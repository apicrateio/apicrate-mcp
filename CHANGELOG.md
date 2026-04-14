# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-14

### Added

- QR Code tool (`apicrate-generate-qr`) — 22 tools across 9 domains.
- Live tool schema fetching from hosted server at startup.
- Typed parameter schemas exposed to MCP clients.

### Fixed

- Async HTTP client with proper lifecycle management.
- Environment variables read at runtime instead of import time.
- HTTP and JSON error handling for failed proxy calls.
- mypy strict mode compliance.

## [0.1.0] - 2026-03-29

### Added

- Initial release with STDIO transport proxy for the ApiCrate hosted MCP server.
- All 21 tools across 8 domains: User Agents, IP Geolocation, Countries, Postal Codes, Timezones, Hashing, Bible, Email Risk.
- Configuration via environment variables (`APICRATE_API_KEY`, `APICRATE_BASE_URL`, `APICRATE_TIMEOUT`).
- Setup examples for Claude Desktop, Claude Code, Cursor, and Windsurf.
- Streamable HTTP connection docs for clients that support it natively.
