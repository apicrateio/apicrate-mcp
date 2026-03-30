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

import json
import os
import sys
import threading
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

_DEFAULT_BASE_URL = "https://api.apicrate.io"
_DEFAULT_TIMEOUT = 30.0

# ---------------------------------------------------------------------------
# Tool definitions — mirrored from the hosted server
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

    response = await client.post("/mcp/", json=payload)
    response.raise_for_status()

    result = response.json()

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


def _make_handler(tool_name: str):
    """Create a handler function for a given tool."""

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

    handler.__name__ = tool_name.replace("-", "_")
    return handler


# Register all tools with FastMCP
for _tool_def in TOOLS:
    _name = _tool_def["name"]
    _desc = _tool_def["description"]
    _handler = _make_handler(_name)

    # Build parameter annotations for FastMCP
    _params = {}
    for pname, pdef in _tool_def.get("params", {}).items():
        ptype = pdef.get("type", "string")
        if ptype in ("string", "str"):
            _params[pname] = (str, pdef.get("description", ""))
        elif ptype in ("number", "float"):
            _params[pname] = (float, pdef.get("description", ""))
        elif ptype in ("integer", "int"):
            _params[pname] = (int, pdef.get("description", ""))
        else:
            _params[pname] = (Any, pdef.get("description", ""))

    mcp.tool(name=_name, description=_desc)(_handler)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the ApiCrate MCP server over STDIO."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
