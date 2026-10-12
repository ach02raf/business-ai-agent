"""Agent LangGraph : agent -> (tools | sensitive_tools [pause humaine]) -> agent -> ...

   START ──▶ agent ──(pas de tool call)──▶ END
              │  ▲
   lecture    │  │
     ┌────────┘  └────────────┐
     ▼                        │
   tools            sensitive_tools   <- interrupt_before = validation humaine
     └────────────────────────┘
"""
import json
import time
import uuid
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from .backends import make_backend
from .config import get_settings
from .guardrails import GuardrailError, audit, check_tool_call, check_user_input, requires_approval
from .llm import SYSTEM_PROMPT, get_llm


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    steps: int


class NoPendingApproval(Exception):
    pass


class PendingApprovalError(Exception):
    pass


def build_graph(llm, backend):
    settings = get_settings()

    def agent_node(state: AgentState):
        steps = state.get("steps", 0)
        if steps >= settings.max_steps:  # garde-fou anti-boucle
            return {"messages": [AIMessage(content="I reached my step limit without finishing. Please rephrase or contact a human agent.")],
                    "steps": steps}
        try:
            response = llm.invoke([SystemMessage(content=SYSTEM_PROMPT)] + state["messages"])
        except Exception as exc:  # noqa: BLE001  (fallback final si le LLM est down)
            audit("llm_failure", error=str(exc))
            response = AIMessage(content="The AI service is temporarily unavailable. Please try again shortly.")
        return {"messages": [response], "steps": steps + 1}

    def route(state: AgentState):
        last = state["messages"][-1]
        calls = getattr(last, "tool_calls", None)
        if not calls:
            return END
        return "sensitive_tools" if any(requires_approval(c["name"]) for c in calls) else "tools"

    def tools_node(state: AgentState):
        last: AIMessage = state["messages"][-1]
        out = []
        for call in last.tool_calls:
            started = time.time()
            try:
                args = check_tool_call(call["name"], call["args"])
                result = _run_with_retries(backend, call["name"], args, settings.tool_retries)
            except GuardrailError as exc:
                result = {"error": "blocked_by_guardrail", "detail": str(exc)}
            except Exception as exc:  # noqa: BLE001
                result = {"error": "tool_failed", "detail": str(exc)}
            audit("tool_call", tool=call["name"], args=call["args"],
                  ok="error" not in result, ms=int((time.time() - started) * 1000))
            out.append(ToolMessage(content=json.dumps(result, ensure_ascii=False),
                                   tool_call_id=call["id"], name=call["name"]))
        return {"messages": out}

    g = StateGraph(AgentState)
    g.add_node("agent", agent_node)
    g.add_node("tools", tools_node)
    g.add_node("sensitive_tools", tools_node)
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", route, {"tools": "tools", "sensitive_tools": "sensitive_tools", END: END})
    g.add_edge("tools", "agent")
    g.add_edge("sensitive_tools", "agent")
    return g.compile(checkpointer=MemorySaver(), interrupt_before=["sensitive_tools"])


def _run_with_retries(backend, name, args, retries):
    last_exc = None
    for _ in range(retries + 1):
        try:
            return backend.call(name, args)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
    raise last_exc


class AgentService:
    def __init__(self, llm=None, backend=None):
        self.graph = build_graph(llm or get_llm(), backend or make_backend(get_settings().tool_backend))

    @staticmethod
    def _cfg(thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}, "recursion_limit": 25}

    def chat(self, message: str, thread_id: str | None = None) -> dict:
        message = check_user_input(message)
        thread_id = thread_id or uuid.uuid4().hex
        cfg = self._cfg(thread_id)
        if self.graph.get_state(cfg).next:
            raise PendingApprovalError("This thread is waiting for human approval (/approve).")
        audit("user_message", thread_id=thread_id)
        self.graph.invoke({"messages": [HumanMessage(content=message)], "steps": 0}, cfg)
        return self._snapshot(thread_id)

    def approve(self, thread_id: str, approve: bool, reason: str = "") -> dict:
        cfg = self._cfg(thread_id)
        state = self.graph.get_state(cfg)
        if not state.next:
            raise NoPendingApproval("No action pending approval for this thread.")
        audit("human_decision", thread_id=thread_id, approved=approve, reason=reason)
        if not approve:
            last: AIMessage = state.values["messages"][-1]
            rejections = [ToolMessage(content=json.dumps({"error": "rejected_by_human", "detail": reason or "Rejected by a human reviewer"}),
                                      tool_call_id=c["id"], name=c["name"]) for c in last.tool_calls]
            self.graph.update_state(cfg, {"messages": rejections}, as_node="sensitive_tools")
        self.graph.invoke(None, cfg)
        return self._snapshot(thread_id)

    def _snapshot(self, thread_id: str) -> dict:
        state = self.graph.get_state(self._cfg(thread_id))
        messages = state.values["messages"]
        start = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
        trace, by_id = [], {}
        for m in messages[start + 1:]:
            if isinstance(m, AIMessage):
                for c in m.tool_calls:
                    entry = {"tool": c["name"], "args": c["args"], "result": None}
                    by_id[c["id"]] = entry
                    trace.append(entry)
            elif isinstance(m, ToolMessage) and m.tool_call_id in by_id:
                by_id[m.tool_call_id]["result"] = json.loads(m.content)
        if state.next:
            last = messages[-1]
            pending = [{"id": c["id"], "tool": c["name"], "args": c["args"]} for c in last.tool_calls]
            return {"thread_id": thread_id, "status": "pending_approval", "answer": None,
                    "pending_actions": pending, "trace": [t for t in trace if t["result"] is not None]}
        return {"thread_id": thread_id, "status": "completed", "answer": messages[-1].content,
                "pending_actions": [], "trace": trace}
