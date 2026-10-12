"""Test d'intégration : appel des tools via un vrai serveur MCP (stdio)."""
from app.backends import MCPBackend


def test_mcp_backend_roundtrip():
    result = MCPBackend().call("get_order", {"order_id": 4521})
    assert result["status"] == "shipped"
