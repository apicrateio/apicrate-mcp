# Contributing to ApiCrate MCP Server

Thanks for your interest in contributing! Here's how to get started.

## Reporting Issues

If you find a bug or have a feature request, please [open an issue](https://github.com/apicrateio/apicrate-mcp/issues) with:

- A clear description of the problem or suggestion
- Steps to reproduce (for bugs)
- Your environment (Python version, MCP client, OS)

## Development Setup

```bash
git clone https://github.com/apicrateio/apicrate-mcp.git
cd apicrate-mcp
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest
```

## Code Style

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
ruff check .
ruff format .
```

And [mypy](https://mypy-lang.org/) for type checking:

```bash
mypy src/
```

## Pull Requests

1. Fork the repository.
2. Create a feature branch from `main`.
3. Make your changes and add tests if applicable.
4. Ensure all checks pass: `ruff check .` and `pytest`.
5. Submit a pull request with a clear description.

## Tool Definitions

Tool definitions in `server.py` mirror the hosted ApiCrate MCP server. If you notice a discrepancy between this package and the live server, please open an issue so we can sync them.

## Code of Conduct

Be kind, be constructive, and assume good intent. We're all here to build something useful.
