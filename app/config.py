"""Configuration lue à chaque appel (facilite les tests)."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _csv(name: str, default: str) -> tuple[str, ...]:
    return tuple(x.strip() for x in os.getenv(name, default).split(",") if x.strip())


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    model: str
    fallback_model: str
    mock_llm: bool
    tool_backend: str
    allowed_tools: tuple[str, ...]
    approval_tools: tuple[str, ...]
    tool_retries: int
    max_steps: int
    tickets_file: str
    api_key: str


def get_settings() -> Settings:
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        model=os.getenv("MODEL", "gpt-4o-mini"),
        fallback_model=os.getenv("FALLBACK_MODEL", "gpt-4.1-mini"),
        mock_llm=os.getenv("MOCK_LLM", "false").lower() in ("1", "true", "yes"),
        tool_backend=os.getenv("TOOL_BACKEND", "local").lower(),
        allowed_tools=_csv("ALLOWED_TOOLS", "search_customer,get_order,create_ticket"),
        approval_tools=_csv("TOOLS_REQUIRING_APPROVAL", "create_ticket"),
        tool_retries=int(os.getenv("TOOL_RETRIES", "1")),
        max_steps=int(os.getenv("MAX_STEPS", "6")),
        tickets_file=os.getenv("TICKETS_FILE", "data/tickets.json"),
        api_key=os.getenv("API_KEY", ""),
    )
