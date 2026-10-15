"""Tests for the ``ledger`` API (watch / agent / get / set / revert)."""

from __future__ import annotations

import pytest

from agentledger import ledger
from agentledger.models import SourceType


@pytest.fixture(autouse=True)
def _memory_ledger() -> None:
    ledger.configure(db_path=":memory:")
    yield
    ledger.configure(db_path=":memory:")


def test_watch_hashes_return_and_stores_verified_receipt() -> None:
    @ledger.watch(key="acme::budget", source_uri="tool://fetch_budget")
    def fetch_budget() -> str:
        return "Approved budget: $500,000"

    result = fetch_budget()
    assert result == "Approved budget: $500,000"

    blamed = ledger.blame("acme::budget")
    assert blamed is not None
    assert blamed["value"] == "Approved budget: $500,000"
    assert blamed["evidence"]["source_type"] == SourceType.TOOL_STDOUT.value
    digest = blamed["evidence"]["raw_artifact_sha256"]
    assert len(digest) == 64
    assert ledger.engine.artifact_exists(digest)

    # Value equals registered artifact content hash
    assert digest == ledger.engine.hash_text("Approved budget: $500,000")


def test_agent_context_links_get_reads_to_set_writes() -> None:
    @ledger.watch(key="acme::budget")
    def fetch_budget() -> str:
        return "Approved budget: $500,000"

    fetch_budget()
    upstream = ledger.blame("acme::budget")
    assert upstream is not None
    upstream_hash = upstream["commit_hash"]

    with ledger.agent("bot-pricer"):
        budget = ledger.get("acme::budget")
        assert budget == "Approved budget: $500,000"
        commit = ledger.set("acme::quote", 75_000)

    assert upstream_hash in commit.causal_read_hashes
    assert commit.agent_id == "bot-pricer"
    assert ledger.get("acme::quote", min_confidence=0.0) == 75_000


def test_revert_upstream_cascades_to_pricer_fact() -> None:
    @ledger.watch(key="acme::budget")
    def fetch_budget() -> str:
        return "Approved budget: $500,000"

    fetch_budget()
    upstream_hash = ledger.blame("acme::budget")["commit_hash"]  # type: ignore[index]

    with ledger.agent("bot-pricer"):
        ledger.get("acme::budget")
        pricer_commit = ledger.set("acme::quote", 75_000)

    quarantined = ledger.revert(upstream_hash)
    assert upstream_hash in quarantined
    assert pricer_commit.commit_hash in quarantined

    assert ledger.get("acme::budget", min_confidence=0.0) is None
    assert ledger.get("acme::quote", min_confidence=0.0) is None
    assert ledger.engine.get_commit(pricer_commit.commit_hash).status == "QUARANTINED"  # type: ignore[union-attr]
