"""Tests for the ApiCrate MCP server."""

from unittest.mock import MagicMock, patch

import pytest


def test_tool_definitions_complete():
    """Verify all 21 tools are registered."""
    from apicrate_mcp.server import TOOLS

    assert len(TOOLS) == 21

    # Every tool should have a name and description
    for tool in TOOLS:
        assert "name" in tool, f"Tool missing 'name': {tool}"
        assert "description" in tool, f"Tool missing 'description': {tool}"
        assert tool["name"].startswith("apicrate-"), (
            f"Tool name should start with 'apicrate-': {tool['name']}"
        )


def test_tool_names_valid():
    """Tool names should match MCP naming convention."""
    import re

    from apicrate_mcp.server import TOOLS

    pattern = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
    for tool in TOOLS:
        assert pattern.match(tool["name"]), f"Invalid tool name: {tool['name']}"


def test_tool_names_unique():
    """No duplicate tool names."""
    from apicrate_mcp.server import TOOLS

    names = [t["name"] for t in TOOLS]
    assert len(names) == len(set(names)), f"Duplicate tool names found: {names}"


def test_all_domains_covered():
    """Verify tools span all 8 expected domains."""
    from apicrate_mcp.server import TOOLS

    names = {t["name"] for t in TOOLS}

    # At least one tool per domain
    assert any("user-agent" in n for n in names), "Missing User Agent tools"
    assert any("geolocate-ip" in n for n in names), "Missing IP Geolocation tools"
    assert any("country" in n or "countries" in n for n in names), "Missing Country tools"
    assert any("postal" in n for n in names), "Missing Postal Code tools"
    assert any("timezone" in n or "convert-time" in n for n in names), "Missing Timezone tools"
    assert any("hash" in n for n in names), "Missing Hashing tools"
    assert any("bible" in n for n in names), "Missing Bible tools"
    assert any("email" in n for n in names), "Missing Email Risk tools"


def test_call_tool_success():
    """Test that _call_tool correctly forwards requests."""
    from apicrate_mcp.server import _call_tool

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "content": [{"type": "text", "text": '{"country_code": "DE"}'}],
        },
    }

    mock_client = MagicMock()
    mock_client.post.return_value = mock_response

    _call_tool(mock_client, "apicrate-lookup-country", {"code": "DE"})

    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "/mcp/"
    payload = call_args[1]["json"]
    assert payload["method"] == "tools/call"
    assert payload["params"]["name"] == "apicrate-lookup-country"
    assert payload["params"]["arguments"] == {"code": "DE"}


def test_call_tool_error():
    """Test that JSON-RPC errors are handled."""
    from apicrate_mcp.server import _call_tool

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {"code": -32600, "message": "Country not found: ZZ"},
    }

    mock_client = MagicMock()
    mock_client.post.return_value = mock_response

    result = _call_tool(mock_client, "apicrate-lookup-country", {"code": "ZZ"})

    assert result["isError"] is True
    assert "Country not found: ZZ" in result["content"][0]["text"]


def test_missing_api_key_exits():
    """Server should exit if APICRATE_API_KEY is not set."""
    from apicrate_mcp.server import _get_client

    with patch.dict("os.environ", {"APICRATE_API_KEY": ""}, clear=False), pytest.raises(SystemExit):
        _get_client()


def test_version():
    """Package version should be set."""
    from apicrate_mcp import __version__

    assert __version__ == "0.1.0"
