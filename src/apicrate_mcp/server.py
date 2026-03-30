"""
ApiCrate MCP Server — STDIO proxy.

Exposes all ApiCrate tools over STDIO by proxying requests to the hosted
MCP server at https://api.apicrate.io/mcp/.  This lets MCP clients that
only support STDIO (or prefer env-var auth) use ApiCrate without
configuring HTTP headers.

Usage:
    APICRATE_API_KEY=ac_usr_... apicrate-mcp
    APICRATE_API_KEY=ac_usr_... python -m apicrate_mcp
"""

import atexit
import inspect
import json
import os
import sys
import threading
from typing import Annotated, Any

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import Field

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

_DEFAULT_BASE_URL = "https://api.apicrate.io"
_DEFAULT_TIMEOUT = 30.0

# ---------------------------------------------------------------------------
# Tool definitions — static fallback, used when the hosted server is
# unreachable at startup.
# ---------------------------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    # User Agents
    {
        "name": "apicrate-parse-user-agent",
        "description": (
            "Parse a single User-Agent string into structured device, browser, "
            "and OS data. Returns detailed classification flags and nested "
            "objects for client, OS, device, and bot information."
        ),
        "params": {
            "user_agent_string": {
                "type": "string",
                "required": True,
                "description": "Full User-Agent header value to parse.",
            }
        },
    },
    {
        "name": "apicrate-parse-user-agents-bulk",
        "description": (
            "Parse multiple User-Agent strings in a single call. Efficiently "
            "processes up to 100 UA strings at once."
        ),
        "params": {
            "user_agent_strings": {
                "type": "list[string]",
                "required": True,
                "description": "List of User-Agent header values to parse. Maximum 100 items.",
            }
        },
    },
    # IP Geolocation
    {
        "name": "apicrate-geolocate-ip",
        "description": (
            "Geolocate an IP address. Returns country, city, ISP, ASN, and VPN/Tor detection flags."
        ),
        "params": {
            "ip": {
                "type": "string",
                "required": True,
                "description": "IPv4 or IPv6 address to geolocate.",
            }
        },
    },
    # Countries
    {
        "name": "apicrate-lookup-country",
        "description": (
            "Look up a country by ISO alpha-2, alpha-3, or numeric code. "
            "Returns full ISO 3166-1 record with capital, currencies, and languages."
        ),
        "params": {
            "code": {
                "type": "string",
                "required": True,
                "description": "ISO 3166-1 alpha-2, alpha-3, or numeric country code (e.g. DE, DEU, 276).",
            }
        },
    },
    {
        "name": "apicrate-search-countries",
        "description": "Search or filter countries by region, sub-region, or name.",
        "params": {
            "query": {
                "type": "string",
                "required": False,
                "description": "Free-text search against country names.",
            },
            "region": {
                "type": "string",
                "required": False,
                "description": "Filter by region (e.g. Europe, Asia).",
            },
            "sub_region": {
                "type": "string",
                "required": False,
                "description": "Filter by sub-region (e.g. Western Europe).",
            },
        },
    },
    {
        "name": "apicrate-validate-country-codes",
        "description": "Validate one or more ISO 3166-1 country codes (max 50).",
        "params": {
            "codes": {
                "type": "list[string]",
                "required": True,
                "description": "List of country codes to validate. Maximum 50 items.",
            }
        },
    },
    # Postal Codes
    {
        "name": "apicrate-lookup-postal-code",
        "description": (
            "Look up a postal code for a given country, returning place name, "
            "administrative region, and coordinates."
        ),
        "params": {
            "country_code": {
                "type": "string",
                "required": True,
                "description": "ISO 3166-1 alpha-2 country code (e.g. DE, US).",
            },
            "postal_code": {
                "type": "string",
                "required": True,
                "description": "The postal code to look up.",
            },
        },
    },
    {
        "name": "apicrate-validate-postal-code",
        "description": (
            "Validate a postal code against a country's format regex and "
            "check whether it exists in the database."
        ),
        "params": {
            "country_code": {
                "type": "string",
                "required": True,
                "description": "ISO 3166-1 alpha-2 country code.",
            },
            "postal_code": {
                "type": "string",
                "required": True,
                "description": "The postal code to validate.",
            },
        },
    },
    {
        "name": "apicrate-search-postal-codes",
        "description": "Search postal codes within a country by place name or code prefix.",
        "params": {
            "country_code": {
                "type": "string",
                "required": True,
                "description": "ISO 3166-1 alpha-2 country code.",
            },
            "query": {
                "type": "string",
                "required": False,
                "description": "Free-text search against place names.",
            },
            "prefix": {
                "type": "string",
                "required": False,
                "description": "Postal code prefix to match.",
            },
        },
    },
    {
        "name": "apicrate-list-postal-systems",
        "description": "List countries with postal code data and their code formats.",
        "params": {
            "query": {
                "type": "string",
                "required": False,
                "description": "Filter countries by name. Omit to list all.",
            }
        },
    },
    {
        "name": "apicrate-get-postal-system",
        "description": (
            "Get postal system details for a specific country, including format, "
            "validation regex, and example codes."
        ),
        "params": {
            "country_code": {
                "type": "string",
                "required": True,
                "description": "ISO 3166-1 alpha-2 country code.",
            }
        },
    },
    {
        "name": "apicrate-validate-postal-codes-bulk",
        "description": (
            "Validate multiple postal codes with format and existence checks. "
            "Each item specifies its own country code. Maximum 50 codes per call."
        ),
        "params": {
            "codes": {
                "type": "list[dict]",
                "required": True,
                "description": "List of objects with 'country_code' and 'postal_code' keys. Maximum 50 items.",
            }
        },
    },
    {
        "name": "apicrate-find-nearby-postal-codes",
        "description": "Find postal codes near a geographic point, ordered by distance.",
        "params": {
            "country_code": {
                "type": "string",
                "required": True,
                "description": "ISO 3166-1 alpha-2 country code.",
            },
            "lat": {
                "type": "number",
                "required": True,
                "description": "Latitude of the search center (-90 to 90).",
            },
            "lng": {
                "type": "number",
                "required": True,
                "description": "Longitude of the search center (-180 to 180).",
            },
            "radius_km": {
                "type": "number",
                "required": True,
                "description": "Search radius in kilometres (0 to 500).",
            },
        },
    },
    # Timezones
    {
        "name": "apicrate-get-timezone-info",
        "description": "Get current time, UTC offset, and DST status for a timezone.",
        "params": {
            "timezone": {
                "type": "string",
                "required": True,
                "description": "IANA timezone name (e.g. Europe/Berlin, America/New_York).",
            }
        },
    },
    {
        "name": "apicrate-convert-time",
        "description": "Convert a time from one timezone to another.",
        "params": {
            "time": {
                "type": "string",
                "required": True,
                "description": "Time to convert (ISO 8601 or HH:MM format).",
            },
            "from_tz": {"type": "string", "required": True, "description": "Source IANA timezone."},
            "to_tz": {"type": "string", "required": True, "description": "Target IANA timezone."},
        },
    },
    # Hashing
    {
        "name": "apicrate-compute-hash",
        "description": "Compute a cryptographic digest (MD5, SHA-1, SHA-256, or SHA-512).",
        "params": {
            "data": {"type": "string", "required": True, "description": "The string to hash."},
            "algorithm": {
                "type": "string",
                "required": True,
                "description": "Hash algorithm: md5, sha1, sha256, or sha512.",
            },
        },
    },
    {
        "name": "apicrate-hash-password",
        "description": (
            "Hash a password with a slow key-derivation function (bcrypt, scrypt, or argon2id)."
        ),
        "params": {
            "password": {
                "type": "string",
                "required": True,
                "description": "The password to hash.",
            },
            "algorithm": {
                "type": "string",
                "required": True,
                "description": "KDF algorithm: bcrypt, scrypt, or argon2id.",
            },
        },
    },
    # Bible
    {
        "name": "apicrate-get-bible-verse",
        "description": "Retrieve a verse or verse range from 30+ Bible translations.",
        "params": {
            "reference": {
                "type": "string",
                "required": True,
                "description": "Verse reference (e.g. 'John 3:16', 'Genesis 1:1-3').",
            },
            "translation": {
                "type": "string",
                "required": False,
                "description": "Translation code (e.g. 'NIV', 'KJV'). Defaults to KJV.",
            },
        },
    },
    {
        "name": "apicrate-search-bible",
        "description": "Search the Bible for verses matching a keyword or phrase.",
        "params": {
            "query": {
                "type": "string",
                "required": True,
                "description": "Keyword or phrase to search for.",
            },
            "translation": {
                "type": "string",
                "required": False,
                "description": "Translation code to search within. Defaults to KJV.",
            },
        },
    },
    # Email Risk
    {
        "name": "apicrate-check-email-risk",
        "description": (
            "Validate an email address and compute a fraud risk score. "
            "Checks syntax, MX records, disposable domain, domain age, "
            "free provider, and abuse list."
        ),
        "params": {
            "email": {
                "type": "string",
                "required": True,
                "description": "Email address to analyse (max 254 characters).",
            }
        },
    },
    {
        "name": "apicrate-check-email-risk-bulk",
        "description": "Validate up to 10 email addresses with risk scores in one call.",
        "params": {
            "emails": {
                "type": "list[string]",
                "required": True,
                "description": "List of email addresses to analyse (1-10 items).",
            }
        },
    },
]


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------


def _get_client() -> httpx.AsyncClient:
    """Create a persistent async HTTP client with auth headers.

    Reads environment variables at call time so that configuration set
    after module import is picked up correctly.
    """
    api_key = os.environ.get("APICRATE_API_KEY", "")
    if not api_key:
        print(
            "Error: APICRATE_API_KEY environment variable is not set.\n"
            "Get your free API key at https://apicrate.io and run:\n\n"
            "  export APICRATE_API_KEY=ac_usr_your_key_here\n",
            file=sys.stderr,
        )
        sys.exit(1)

    base_url = os.environ.get("APICRATE_BASE_URL", _DEFAULT_BASE_URL)
    timeout = float(os.environ.get("APICRATE_TIMEOUT", str(_DEFAULT_TIMEOUT)))

    return httpx.AsyncClient(
        base_url=base_url,
        headers={"X-API-Key": api_key},
        timeout=timeout,
    )


async def _call_tool(
    client: httpx.AsyncClient, name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """
    Forward a tool call to the hosted ApiCrate MCP server.

    Uses the JSON-RPC style MCP Streamable HTTP protocol:
    POST /mcp/ with a tools/call request.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": arguments,
        },
    }

    try:
        response = await client.post("/mcp/", json=payload)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"HTTP request failed: {exc}"}],
        }

    try:
        result = response.json()
    except (ValueError, UnicodeDecodeError):
        return {
            "isError": True,
            "content": [
                {"type": "text", "text": f"Invalid JSON response (HTTP {response.status_code})"}
            ],
        }

    # Handle JSON-RPC error
    if "error" in result:
        error = result["error"]
        return {
            "isError": True,
            "content": [{"type": "text", "text": error.get("message", "Unknown error")}],
        }

    return result.get("result", result)


# ---------------------------------------------------------------------------
# MCP server setup
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "ApiCrate",
    instructions=(
        "Access 21 data tools: IP geolocation, email risk, postal codes, "
        "countries, timezones, user-agent parsing, hashing, and Bible search. "
        "Powered by apicrate.io."
    ),
)

# We store the HTTP client at module level, initialized lazily
_client: httpx.AsyncClient | None = None
_client_lock = threading.Lock()


def _ensure_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = _get_client()
    return _client


def _close_client() -> None:
    """Best-effort synchronous close of the async HTTP client at exit."""
    global _client
    if _client is not None:
        try:
            import asyncio

            asyncio.get_event_loop().run_until_complete(_client.aclose())
        except Exception:  # noqa: BLE001
            pass
        _client = None


atexit.register(_close_client)


_TYPE_MAP: dict[str, Any] = {
    "string": str,
    "str": str,
    "number": float,
    "float": float,
    "integer": int,
    "int": int,
    "list[string]": list[str],
    "list[dict]": list[dict[str, Any]],
}


def _make_handler(tool_name: str, params: dict[str, dict[str, Any]]):
    """Create a handler function for a given tool with typed parameters.

    Builds a proper ``inspect.Signature`` so that FastMCP exposes correct
    parameter types, descriptions, and required/optional status in the
    MCP tool schema.
    """

    async def handler(**kwargs: Any) -> str:
        client = _ensure_client()
        result = await _call_tool(client, tool_name, kwargs)

        # If the result has isError, propagate as error text
        if isinstance(result, dict) and result.get("isError"):
            content = result.get("content", [])
            text_parts = [c["text"] for c in content if c.get("type") == "text"]
            raise Exception("\n".join(text_parts) if text_parts else "Tool call failed")

        # Extract text content from MCP response
        if isinstance(result, dict) and "content" in result:
            content = result["content"]
            text_parts = [c["text"] for c in content if c.get("type") == "text"]
            return "\n".join(text_parts) if text_parts else json.dumps(result)

        return json.dumps(result, indent=2)

    # Build typed signature for FastMCP schema generation
    sig_params = []
    annotations: dict[str, Any] = {}
    for pname, pdef in params.items():
        base_type = _TYPE_MAP.get(pdef.get("type", "string"), Any)
        required = pdef.get("required", True)
        desc = pdef.get("description", "")

        if required:
            ann = Annotated[base_type, Field(description=desc)]  # type: ignore[valid-type]
            param = inspect.Parameter(pname, inspect.Parameter.KEYWORD_ONLY, annotation=ann)
        else:
            ann = Annotated[base_type | None, Field(description=desc)]  # type: ignore[valid-type]
            param = inspect.Parameter(
                pname, inspect.Parameter.KEYWORD_ONLY, default=None, annotation=ann
            )

        sig_params.append(param)
        annotations[pname] = ann

    annotations["return"] = str
    handler.__signature__ = inspect.Signature(sig_params)  # type: ignore[assignment]
    handler.__annotations__ = annotations
    handler.__name__ = tool_name.replace("-", "_")
    return handler


def _register_tools(tools: list[dict[str, Any]]) -> None:
    """Register a list of tool definitions with the FastMCP server."""
    for tool_def in tools:
        name = tool_def["name"]
        desc = tool_def["description"]
        handler = _make_handler(name, tool_def.get("params", {}))
        mcp.tool(name=name, description=desc)(handler)


def _json_schema_to_params(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Convert a JSON Schema ``properties`` object to our internal param format."""
    properties = schema.get("properties", {})
    required_set = set(schema.get("required", []))
    params: dict[str, dict[str, Any]] = {}

    for pname, pdef in properties.items():
        # Map JSON Schema type to our type strings
        json_type = pdef.get("type", "string")
        if json_type == "array":
            items_type = pdef.get("items", {}).get("type", "string")
            ptype = "list[dict]" if items_type == "object" else "list[string]"
        elif json_type == "number":
            ptype = "number"
        elif json_type == "integer":
            ptype = "integer"
        else:
            ptype = "string"

        params[pname] = {
            "type": ptype,
            "required": pname in required_set,
            "description": pdef.get("description", ""),
        }

    return params


def _fetch_live_tools() -> list[dict[str, Any]] | None:
    """Fetch the tool list from the hosted MCP server.

    Returns our internal tool format, or ``None`` on any failure.
    """
    api_key = os.environ.get("APICRATE_API_KEY", "")
    if not api_key:
        return None

    base_url = os.environ.get("APICRATE_BASE_URL", _DEFAULT_BASE_URL)

    payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    try:
        with httpx.Client(base_url=base_url, headers={"X-API-Key": api_key}, timeout=10) as client:
            response = client.post("/mcp/", json=payload)
            response.raise_for_status()
            data = response.json()
    except Exception:  # noqa: BLE001
        return None

    result = data.get("result", {})
    raw_tools = result.get("tools", [])
    if not raw_tools:
        return None

    tools = []
    for t in raw_tools:
        tools.append(
            {
                "name": t["name"],
                "description": t.get("description", ""),
                "params": _json_schema_to_params(t.get("inputSchema", {})),
            }
        )
    return tools


# Register static tools immediately so the module is usable in tests
# without a network connection. main() re-registers from the live server.
_register_tools(TOOLS)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the ApiCrate MCP server over STDIO."""
    live = _fetch_live_tools()
    if live is not None:
        # Clear static registrations and use the live set
        mcp._tool_manager._tools.clear()
        _register_tools(live)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
