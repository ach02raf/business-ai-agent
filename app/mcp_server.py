"""Serveur MCP exposant les mêmes tools.

    python -m app.mcp_server                      # stdio (Claude Desktop, agent)
    MCP_TRANSPORT=streamable-http python -m app.mcp_server
"""
import os

from mcp.server.fastmcp import FastMCP

from .tools import TOOLS

mcp = FastMCP("business-tools")

for spec in TOOLS.values():
    mcp.tool(name=spec.name, description=spec.description)(spec.func)

if __name__ == "__main__":
    mcp.run(transport=os.getenv("MCP_TRANSPORT", "stdio"))
