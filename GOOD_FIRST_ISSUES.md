# Good First Issues

Copy any block below into a new GitHub Issue. Each is scoped for a first-time contributor.

---

## Issue 1 — CrewAI adapter

**Title:** `feat: CrewAI memory adapter backed by AgentLedger`

**Labels:** `good first issue`, `integration`, `help wanted`

**Body:**

```markdown
### Problem
CrewAI crews share scratchpad state without provenance. A poisoned tool result can cascade across agents with no rollback.

### Goal
Ship `agentledger.adapters.crewai` that implements CrewAI's memory/storage interface on top of `AgentLedgerEngine`.

### Acceptance criteria
- [ ] `CrewAILedgerMemory` (or similar) wraps `register_artifact` / `read_facts` / `commit` / `revert_cascade`
- [ ] Example crew script under `examples/crewai_demo.py` that fails closed on `UNVERIFIED_RECEIPT`
- [ ] Unit tests with CrewAI mocked or as an optional extra `pip install -e ".[crewai]"`
- [ ] README section: "Using with CrewAI"

### Notes
Keep core deps unchanged — put `crewai` behind an optional extra.
```

---

## Issue 2 — LangGraph checkpointer adapter

**Title:** `feat: LangGraph checkpointer that records causal_read_hashes`

**Labels:** `good first issue`, `integration`, `help wanted`

**Body:**

```markdown
### Problem
LangGraph checkpointing persists state, but does not enforce evidence receipts or causal quarantine across node writes.

### Goal
Implement an `AgentLedgerSaver` / checkpointer adapter that:
1. Registers node I/O as artifacts
2. Commits facts with `causal_read_hashes` from prior reads
3. Exposes a graph interrupt path when the firewall raises

### Acceptance criteria
- [ ] Adapter module under `src/agentledger/adapters/langgraph.py`
- [ ] Optional extra `langgraph`
- [ ] Minimal graph example + pytest covering firewall block + cascade
- [ ] Docs snippet for LangGraph users

### Notes
Prefer composing with existing LangGraph BaseCheckpointSaver patterns rather than forking LangGraph.
```

---

## Issue 3 — Postgres / pgvector storage backend

**Title:** `feat: optional Postgres + pgvector storage backend`

**Labels:** `good first issue`, `storage`, `help wanted`

**Body:**

```markdown
### Problem
SQLite is perfect for local/dev, but teams want a shared multi-process ledger with optional embedding search over fact values / excerpts.

### Goal
Add `AgentLedgerEngine` backend selection:
- default: SQLite (current)
- optional: Postgres with a `facts` embedding column via pgvector

### Acceptance criteria
- [ ] `db_url` / backend flag without breaking `.agentledger/ledger.db` default
- [ ] Schema migration docs for Postgres
- [ ] `similarity_search(query, k)` optional API behind the pgvector extra
- [ ] CI job or tox env that skips when `AGENTLEDGER_PG_URL` is unset
- [ ] Firewall + cascade semantics identical to SQLite

### Notes
Do not add Postgres to core dependencies — use `pip install -e ".[postgres]"`.
```

---

## Issue 4 — Web DAG visualizer

**Title:** `feat: local web UI for the Causal Lineage Graph`

**Labels:** `good first issue`, `frontend`, `help wanted`

**Body:**

```markdown
### Problem
`agentledger log` is great in a terminal; stakeholders want a clickable DAG of commits and quarantine state.

### Goal
A tiny local viewer (FastAPI or stdlib http.server + static HTML) that reads the ledger and renders the causal graph.

### Acceptance criteria
- [ ] `agentledger serve` (or `python -m agentledger.viz`) on localhost
- [ ] Nodes show agent_id, fact keys, status badge (VALIDATED / QUARANTINED)
- [ ] Edges follow `causal_read_hashes`
- [ ] Clicking a node shows blame / evidence receipt
- [ ] No new *required* core dependency (optional `[viz]` extra OK)

### Notes
Keep the UI minimal — one page, high contrast, no heavy SPA framework required.
```

---

## Issue 5 — Markdown audit exporter

**Title:** `feat: export ledger audit trail to Markdown`

**Labels:** `good first issue`, `dx`, `help wanted`

**Body:**

```markdown
### Problem
Compliance / postmortems need a portable audit of what each agent wrote, with receipts and quarantine history.

### Goal
`agentledger export --format md --out AUDIT.md` that dumps commits, facts, evidence, and status.

### Acceptance criteria
- [ ] CLI command `export` with `--format md` (JSON optional stretch)
- [ ] Includes commit hash, agent, timestamp, status, causal parents, fact payload, evidence SHA
- [ ] Quarantined commits clearly marked
- [ ] Pytest golden-file or snapshot for a seeded ledger
- [ ] README docs

### Notes
Pure Python + existing models — no new dependencies.
```

---

## Issue 6 — Webhook alert on quarantine

**Title:** `feat: webhook / Slack alert when revert_cascade quarantines commits`

**Labels:** `good first issue`, `ops`, `help wanted`

**Body:**

```markdown
### Problem
When the Domino Rollback Engine quarantines a chain, on-call should know immediately.

### Goal
Optional webhook notifier fired from `revert_cascade` (and/or CLI `revert`) with a signed JSON payload of quarantined hashes.

### Acceptance criteria
- [ ] Env config: `AGENTLEDGER_WEBHOOK_URL` (no-op when unset)
- [ ] POST JSON: `{ "event": "quarantine", "root": "...", "quarantined": [...], "timestamp": ... }`
- [ ] Timeouts + non-blocking failure (ledger write must not roll back if webhook fails)
- [ ] Unit tests with `httpx`/`urllib` mocked
- [ ] Docs for Slack incoming webhook mapping

### Notes
Prefer stdlib `urllib.request` to avoid new core deps; `httpx` only if already pulled transitively and tested offline.
```
