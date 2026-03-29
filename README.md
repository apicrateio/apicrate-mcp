# ApiCrate MCP Server

[![PyPI version](https://img.shields.io/pypi/v/apicrate-mcp)](https://pypi.org/project/apicrate-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

Connect any MCP-compatible AI agent to **21 data tools** across 8 domains — IP geolocation, email risk scoring, postal codes, countries, timezones, user-agent parsing, cryptographic hashing, and Bible search.

This package provides a **local STDIO transport** for the [ApiCrate](https://apicrate.io) MCP server. It proxies tool calls from your MCP client to the hosted API, so your API key stays in an environment variable instead of a config file.

> You can also connect directly to the hosted server via **Streamable HTTP** at `https://api.apicrate.io/mcp/` — no install needed. See [HTTP Setup](#streamable-http-no-install) below.

## Quick Start

### 1. Get your API key

Sign up free at [apicrate.io](https://apicrate.io) — no credit card required.

### 2. Install

```bash
pip install apicrate-mcp
```

Or run without installing:

```bash
uvx apicrate-mcp
```

### 3. Configure your client

<details open>
<summary><strong>Claude Desktop</strong></summary>

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "apicrate": {
      "command": "apicrate-mcp",
      "env": {
        "APICRATE_API_KEY": "ac_usr_your_key_here"
      }
    }
  }
}
```

</details>

<details>
<summary><strong>Claude Code</strong></summary>

```bash
claude mcp add apicrate -- apicrate-mcp
```

Then set your key:

```bash
export APICRATE_API_KEY=ac_usr_your_key_here
```

Or add a `.mcp.json` to your project root:

```json
{
  "mcpServers": {
    "apicrate": {
      "command": "apicrate-mcp",
      "env": {
        "APICRATE_API_KEY": "ac_usr_your_key_here"
      }
    }
  }
}
```

</details>

<details>
<summary><strong>Cursor</strong></summary>

Add to `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "apicrate": {
      "command": "apicrate-mcp",
      "env": {
        "APICRATE_API_KEY": "ac_usr_your_key_here"
      }
    }
  }
}
```

</details>

<details>
<summary><strong>Windsurf</strong></summary>

Add to `~/.codeium/windsurf/mcp_settings.json`:

```json
{
  "mcpServers": {
    "apicrate": {
      "command": "apicrate-mcp",
      "env": {
        "APICRATE_API_KEY": "ac_usr_your_key_here"
      }
    }
  }
}
```

</details>

### Streamable HTTP (no install)

If your client supports Streamable HTTP, skip the install and connect directly:

```json
{
  "mcpServers": {
    "apicrate": {
      "type": "streamableHttp",
      "url": "https://api.apicrate.io/mcp/",
      "headers": {
        "X-API-Key": "ac_usr_your_key_here"
      }
    }
  }
}
```

### 4. Verify

Ask your agent:

> "What country has code DE?"

It should call `apicrate-lookup-country` and return information about Germany.

## Tools

### User Agents

| Tool | Description | Credits |
|------|-------------|---------|
| `apicrate-parse-user-agent` | Parse browser, OS, device & bot from a UA string | 2 |
| `apicrate-parse-user-agents-bulk` | Batch parse up to 100 UA strings | 1/UA |

### IP Geolocation

| Tool | Description | Credits |
|------|-------------|---------|
| `apicrate-geolocate-ip` | Country, city, ISP, ASN & VPN/Tor detection | 5 |

### Countries

| Tool | Description | Credits |
|------|-------------|---------|
| `apicrate-lookup-country` | Full ISO 3166-1 record — capital, currencies, languages | 1 |
| `apicrate-search-countries` | Filter by region, sub-region, or query | 3 |
| `apicrate-validate-country-codes` | Validate up to 50 country codes in one call | 1/code |

### Postal Codes

| Tool | Description | Credits |
|------|-------------|---------|
| `apicrate-lookup-postal-code` | Resolve to city, admin regions & coordinates | 2 |
| `apicrate-validate-postal-code` | Check format validity and database existence | 1 |
| `apicrate-search-postal-codes` | Search by prefix or place name | 3 |
| `apicrate-list-postal-systems` | List all countries with postal code data | 2 |
| `apicrate-get-postal-system` | Format, regex & examples for a country | 2 |
| `apicrate-validate-postal-codes-bulk` | Batch validate up to 50 postal codes | 2/code |
| `apicrate-find-nearby-postal-codes` | Find codes within a radius of a GPS point | 5 |

### Timezones

| Tool | Description | Credits |
|------|-------------|---------|
| `apicrate-get-timezone-info` | Current time, UTC offset & DST status | 1 |
| `apicrate-convert-time` | Convert time between two timezones | 1 |

### Hashing

| Tool | Description | Credits |
|------|-------------|---------|
| `apicrate-compute-hash` | MD5, SHA-1, SHA-256, or SHA-512 | 1 |
| `apicrate-hash-password` | bcrypt, scrypt, or argon2id | 2 |

### Bible

| Tool | Description | Credits |
|------|-------------|---------|
| `apicrate-get-bible-verse` | Fetch a verse or range across 30+ translations | 1 |
| `apicrate-search-bible` | Full-text search across translations | 3 |

### Email Risk

| Tool | Description | Credits |
|------|-------------|---------|
| `apicrate-check-email-risk` | Syntax, MX, disposable, domain age, abuse list | 4 |
| `apicrate-check-email-risk-bulk` | Bulk assess up to 10 emails | 4/email |

## Example Prompts

Once connected, try these:

- "Where is IP 203.0.113.5 located?"
- "What city is postal code EC1A 1BB in?"
- "Parse this User-Agent string for me"
- "Convert 9am London time to Tokyo"
- "Hash this password with argon2id"
- "Look up John 3:16 in the NIV"
- "Is this email address risky: test@tempmail.com?"
- "Find postal codes within 10km of Berlin's center"

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `APICRATE_API_KEY` | *(required)* | Your API key from [apicrate.io](https://apicrate.io) |
| `APICRATE_BASE_URL` | `https://api.apicrate.io` | API base URL (for testing/self-hosted) |
| `APICRATE_TIMEOUT` | `30` | HTTP request timeout in seconds |

## Credits & Pricing

MCP tool calls consume credits from a daily pool, separate from REST API quota.

| Plan | Credits/day | Price |
|------|-------------|-------|
| **Starter** | 100 | Free |
| **Pro** | 50,000 | $19/mo |
| **Enterprise** | Unlimited | Custom |

Every response includes quota headers (`X-Quota-Limit`, `X-Quota-Remaining`, `X-Quota-Reset`) so you always know your usage.

## Development

```bash
# Clone the repo
git clone https://github.com/apicrate/apicrate-mcp.git
cd apicrate-mcp

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Run the server locally
APICRATE_API_KEY=ac_usr_your_key apicrate-mcp
```

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

[MIT](LICENSE)

## Links

- [ApiCrate Website](https://apicrate.io)
- [API Documentation](https://apicrate.io/docs/)
- [MCP Documentation](https://apicrate.io/docs/s/mcp/index.html)
- [Tool Reference](https://apicrate.io/docs/s/mcp/tools/index.html)
- [Status Page](https://apicrate.io/status/)
- [Community](https://apicrate.io/community/)
