"""FastMCP server — AgentLedger tools for Cursor, Claude Code, and LangGraph."""

from __future__ import annotations

import os
from typing import Any

try:
    # mcp 1.x
    from mcp.server.fastmcp import FastMCP
except ModuleNotFoundError:  # pragma: no cover - mcp 2.x rename
    from mcp.server.mcpserver import MCPServer as FastMCP

from agentledger.engine import AgentLedgerEngine, ProvenanceFirewallError
from agentledger.models import EvidenceAnchor, MemoryFact, SourceType

mcp = FastMCP("AgentLedger")

_DEFAULT_DB = ".agentledger/ledger.db"


def _db_path() -> str:
    return os.environ.get("AGENTLEDGER_DB", _DEFAULT_DB)


def _engine() -> AgentLedgerEngine:
    return AgentLedgerEngine(_db_path())


@mcp.tool()
def ledger_register_evidence(raw_output: str) -> dict[str, Any]:
    """Register raw tool/scrape stdout and return its SHA-256 evidence receipt.

    Call this before ``ledger_commit`` so the Provenance Firewall can verify
    that ``evidence_sha256`` refers to a real runtime artifact.
    """
    engine = _engine()
    try:
        digest = engine.register_artifact(raw_output)
        return {"ok": True, "sha256": digest, "bytes": len(raw_output.encode("utf-8"))}
    finally:
        engine.close()


@mcp.tool()
def ledger_read(
    namespace: str | None = None,
    min_confidence: float = 0.4,
) -> dict[str, Any]:
    """Read active VALIDATED facts on ``main`` above ``min_confidence``.

    Returns facts plus ``causal_read_hashes`` — pass that list into the next
    ``ledger_commit`` so downstream writes form a causal lineage graph.
    """
    engine = _engine()
    try:
        facts, hashes = engine.read_facts(
            namespace=namespace,
            min_confidence=min_confidence,
        )
        return {"ok": True, "facts": facts, "causal_read_hashes": hashes}
    finally:
        engine.close()


@mcp.tool()
def ledger_commit(
    agent_id: str,
    namespace: str,
    entity_key: str,
    value: str,
    evidence_sha256: str,
    source_uri: str,
    excerpt: str,
    causal_read_hashes: list[str] | None = None,
    initial_confidence: float = 0.9,
    half_life_hours: float = 720.0,
) -> dict[str, Any]:
    """Commit a namespaced fact with a verified evidence receipt.

    The Provenance Firewall rejects commits whose ``evidence_sha256`` is not
    present in the artifact registry (``UNVERIFIED_RECEIPT``) and blocks
    low-confidence overwrites of stronger active facts.
    """
    engine = _engine()
    try:
        fact = MemoryFact(
            namespace=namespace,
            entity_key=entity_key,
            value=value,
            initial_confidence=initial_confidence,
            half_life_hours=half_life_hours,
            evidence=EvidenceAnchor(
                source_type=SourceType.TOOL_STDOUT,
                source_uri=source_uri,
                raw_artifact_sha256=evidence_sha256,
                excerpt=excerpt,
            ),
        )
        commit = engine.commit(
            agent_id=agent_id,
            facts=[fact],
            causal_read_hashes=list(causal_read_hashes or []),
            strict_evidence=True,
        )
        return {"ok": True, "commit": commit.model_dump(mode="json")}
    except ProvenanceFirewallError as exc:
        return {"ok": False, "error": "provenance_firewall", "detail": str(exc)}
    finally:
        engine.close()


@mcp.tool()
def ledger_blame(entity_key: str) -> dict[str, Any]:
    """Return provenance for an active entity key (agent, commit, confidence, receipt).

    ``entity_key`` may be bare (``tier``) or namespaced (``acme_corp::tier``).
    """
    engine = _engine()
    try:
        hit = engine.blame(entity_key)
        if hit is None:
            return {"ok": False, "error": "not_found", "entity_key": entity_key}
        return {"ok": True, "blame": hit}
    finally:
        engine.close()


@mcp.tool()
def ledger_revert_cascade(commit_hash: str) -> dict[str, Any]:
    """BFS-quarantine ``commit_hash`` and every causally downstream dependent.

    Walks ``causal_read_hashes`` to mark the poison root and all derived
    commits as ``QUARANTINED`` while leaving unrelated commits ``VALIDATED``.
    """
    engine = _engine()
    try:
        # Allow unique prefixes for agent convenience.
        if len(commit_hash) < 64:
            resolved = engine.resolve_commit_prefix(commit_hash)
            commit_hash = resolved.commit_hash
        quarantined = engine.revert_cascade(commit_hash)
        return {"ok": True, "quarantined_commit_hashes": quarantined}
    except (KeyError, ValueError) as exc:
        return {"ok": False, "error": "not_found", "detail": str(exc)}
    finally:
        engine.close()


def main() -> None:
    """Run the AgentLedger MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
