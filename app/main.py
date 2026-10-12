"""API FastAPI : /chat, /approve, /tools, /tickets, /health."""
import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .agent import AgentService, NoPendingApproval, PendingApprovalError
from .config import get_settings
from .guardrails import GuardrailError
from .tools import TOOLS, list_tickets

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

_service: AgentService | None = None


def get_service() -> AgentService:
    global _service
    if _service is None:
        _service = AgentService()
    return _service


def reset_service() -> None:  # utile pour les tests
    global _service
    _service = None


def require_api_key(x_api_key: str | None = Header(default=None)):
    expected = get_settings().api_key
    if expected and not secrets.compare_digest(x_api_key or "", expected):
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key")


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_service()
    yield


app = FastAPI(title="Business AI Agent", version="1.0.0", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    thread_id: str | None = None


class ApproveRequest(BaseModel):
    thread_id: str
    approve: bool
    reason: str = ""


@app.get("/health")
def health():
    s = get_settings()
    return {"status": "ok", "tool_backend": s.tool_backend,
            "llm": "mock" if (s.mock_llm or not s.openai_api_key) else s.model}


@app.get("/tools", dependencies=[Depends(require_api_key)])
def tools():
    s = get_settings()
    return [{"name": t.name, "description": t.description, "allowed": t.name in s.allowed_tools,
             "requires_approval": t.name in s.approval_tools, "schema": t.schema.model_json_schema()}
            for t in TOOLS.values()]


@app.post("/chat", dependencies=[Depends(require_api_key)])
def chat(req: ChatRequest):
    try:
        return get_service().chat(req.message, req.thread_id)
    except GuardrailError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PendingApprovalError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/approve", dependencies=[Depends(require_api_key)])
def approve(req: ApproveRequest):
    try:
        return get_service().approve(req.thread_id, req.approve, req.reason)
    except NoPendingApproval as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/tickets", dependencies=[Depends(require_api_key)])
def tickets():
    return list_tickets()
