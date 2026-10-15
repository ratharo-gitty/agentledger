# Contributing to AgentLedger

Thanks for helping make multi-agent memory auditable.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -v
ruff check .
agentledger demo
```

## Project layout

```
src/agentledger/
  models.py       # EvidenceAnchor, MemoryFact, MemoryCommit
  engine.py       # SQLite ledger + Provenance Firewall + BFS quarantine
  cli.py          # Typer + Rich (demo / log / blame / revert / seed / mcp)
  mcp_server.py   # FastMCP tools for Cursor / Claude / LangGraph
tests/
  test_engine.py  # Firewall, decay, cascade, MCP tools
```

## Rules

1. **Python 3.10+** with strict type hints on public APIs.
2. **Pydantic v2 only** — `model_dump()`, `model_dump_json()`, `model_validate()`. Never `.dict()` / `.json()`.
3. **Core dependencies only**: `pydantic`, `typer`, `rich`, `mcp`. Storage via stdlib `sqlite3` unless a proposal adds an optional extra.
4. Keep modules under `src/agentledger/` focused and modular.
5. CLI output stays high-contrast via Rich `Panel` / `Table` / `Tree`.
6. Do not open a PR unless `pytest -v` and `ruff check .` are green.

## Pull requests

- One concern per PR when possible.
- Describe the behavior change and how you verified it.
- Update `README.md` if you add CLI commands or MCP tools.
- New storage/adapters should land behind optional extras and keep the default SQLite path zero-config.

## Good first issues

See [GOOD_FIRST_ISSUES.md](GOOD_FIRST_ISSUES.md) for six ready-to-file contributor tickets (CrewAI, LangGraph, Postgres, DAG visualizer, Markdown exporter, quarantine webhooks).

## Security

- Artifact hashes and commit hashes are the trust boundary — never weaken the Provenance Firewall in “demo mode” defaults.
- Keep production ledger paths and any future signing secrets out of source control (`.agentledger/` is gitignored).
