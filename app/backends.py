"""Backends d'exécution des tools : local, MCP (stdio) et fallback MCP -> local."""
import asyncio
import json
import logging
import sys

from .tools import TOOLS

log = logging.getLogger(__name__)


class LocalBackend:
    def call(self, name: str, args: dict) -> dict:
        return TOOLS[name].func(**args)


class MCPBackend:
    """Appelle les tools via un vrai serveur MCP lancé en sous-processus (stdio)."""

    async def _call(self, name: str, args: dict) -> dict:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(command=sys.executable, args=["-m", "app.mcp_server"])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, args)
        text = "".join(getattr(c, "text", "") for c in result.content)
        if result.isError:
            raise RuntimeError(text or "MCP tool error")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"result": text}

    def call(self, name: str, args: dict) -> dict:
        return asyncio.run(self._call(name, args))


class FallbackBackend:
    def __init__(self, primary, fallback):
        self.primary, self.fallback = primary, fallback

    def call(self, name: str, args: dict) -> dict:
        try:
            return self.primary.call(name, args)
        except Exception as exc:  # noqa: BLE001
            log.warning("Primary backend failed (%s) -> fallback local", exc)
            return self.fallback.call(name, args)


def make_backend(kind: str):
    if kind == "mcp":
        return FallbackBackend(MCPBackend(), LocalBackend())
    return LocalBackend()
