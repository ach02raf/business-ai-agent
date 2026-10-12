"""Guardrails : validation d'entrée, allowlist de tools, validation d'arguments,
human-in-the-loop, audit log."""
import json
import logging
import re

from pydantic import ValidationError

from .config import get_settings
from .tools import TOOLS

audit_logger = logging.getLogger("audit")

MAX_INPUT_CHARS = 2000
INJECTION_PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above) (instructions|rules)",
    r"disregard .{0,30}(rules|instructions)",
    r"reveal .{0,30}system prompt",
    r"you are now (?!able)",
]


class GuardrailError(Exception):
    """Une règle de sécurité a bloqué l'action."""


def check_user_input(text: str) -> str:
    if not text or not text.strip():
        raise GuardrailError("Empty message")
    if len(text) > MAX_INPUT_CHARS:
        raise GuardrailError(f"Message too long (max {MAX_INPUT_CHARS} chars)")
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            raise GuardrailError("Potential prompt injection detected")
    return text.strip()


def check_tool_call(name: str, args: dict) -> dict:
    """Vérifie l'allowlist puis valide les arguments. Retourne les arguments nettoyés."""
    settings = get_settings()
    if name not in settings.allowed_tools or name not in TOOLS:
        raise GuardrailError(f"Tool '{name}' is not allowed")
    try:
        return TOOLS[name].schema(**args).model_dump()
    except ValidationError as e:
        problems = "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())
        raise GuardrailError(f"Invalid arguments for '{name}': {problems}") from e


def requires_approval(name: str) -> bool:
    return name in get_settings().approval_tools


def audit(event: str, **fields) -> None:
    audit_logger.info(json.dumps({"event": event, **fields}, default=str, ensure_ascii=False))
