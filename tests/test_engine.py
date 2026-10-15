"""Phase 1 pytest suite: artifacts, firewall rules, decay, 4-agent cascade."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from agentledger.engine import AgentLedgerEngine, ProvenanceFirewallError
from agentledger.models import EvidenceAnchor, MemoryFact, SourceType


@pytest.fixture
def engine() -> AgentLedgerEngine:
    with AgentLedgerEngine(":memory:") as eng:
        yield eng


def _tool_fact(
    engine: AgentLedgerEngine,
    *,
    namespace: str,
    entity_key: str,
    value: object,
    raw_text: str,
    confidence: float = 0.9,
    half_life_hours: float = 720.0,
    source_uri: str = "tool://test",
) -> MemoryFact:
    digest = engine.register_artifact(raw_text)
    return MemoryFact(
        namespace=namespace,
        entity_key=entity_key,
        value=value,
        initial_confidence=confidence,
        half_life_hours=half_life_hours,
        evidence=EvidenceAnchor(
            source_type=SourceType.TOOL_STDOUT,
            source_uri=source_uri,
            raw_artifact_sha256=digest,
            excerpt=raw_text[:80],
        ),
    )


def _human_fact(
    *,
    namespace: str,
    entity_key: str,
    value: object,
    confidence: float = 0.9,
) -> MemoryFact:
    return MemoryFact(
        namespace=namespace,
        entity_key=entity_key,
        value=value,
        initial_confidence=confidence,
        evidence=EvidenceAnchor(
            source_type=SourceType.HUMAN_VERIFIED,
            source_uri="human://tester",
            raw_artifact_sha256="0" * 64,
            excerpt="human verified",
        ),
    )


# --------------------------------------------------------------------------- artifacts + commit


def test_register_artifact_and_valid_commit(engine: AgentLedgerEngine) -> None:
    raw = "scrape: user_id=42 plan=pro"
    digest = engine.register_artifact(raw)
    assert len(digest) == 64
    assert engine.artifact_exists(digest)

    fact = _tool_fact(
        engine,
        namespace="crm",
        entity_key="user.plan",
        value="pro",
        raw_text=raw,
        confidence=0.92,
    )
    # register_artifact inside _tool_fact reuses same digest via INSERT OR IGNORE
    commit = engine.commit(agent_id="agent-ingest", facts=[fact], causal_read_hashes=[])

    assert commit.status == "VALIDATED"
    assert len(commit.commit_hash) == 64
    assert commit.parent_hash is None
    assert commit.branch == "main"
    assert engine.get_head("main") == commit.commit_hash

    facts, hashes = engine.read_facts(namespace="crm", min_confidence=0.4)
    assert len(facts) == 1
    assert facts[0]["entity_key"] == "user.plan"
    assert facts[0]["value"] == "pro"
    assert hashes == [commit.commit_hash]

    blamed = engine.blame("user.plan")
    assert blamed is not None
    assert blamed["agent_id"] == "agent-ingest"
    assert blamed["commit_hash"] == commit.commit_hash
    assert blamed["evidence"]["raw_artifact_sha256"] == fact.evidence.raw_artifact_sha256


# --------------------------------------------------------------------------- firewall rule 1


def test_firewall_blocks_unverified_artifact_receipt(engine: AgentLedgerEngine) -> None:
    hallucinated = MemoryFact(
        namespace="crm",
        entity_key="user.plan",
        value="enterprise",
        initial_confidence=0.99,
        evidence=EvidenceAnchor(
            source_type=SourceType.HTTP_RESPONSE,
            source_uri="https://example.invalid/api",
            raw_artifact_sha256="b" * 64,  # never registered
            excerpt="hallucinated receipt",
        ),
    )
    with pytest.raises(ProvenanceFirewallError, match="UNVERIFIED_RECEIPT"):
        engine.commit(agent_id="hallucinator", facts=[hallucinated])

    facts, hashes = engine.read_facts(min_confidence=0.0)
    assert facts == []
    assert hashes == []


def test_human_verified_bypasses_artifact_check(engine: AgentLedgerEngine) -> None:
    fact = _human_fact(namespace="ops", entity_key="oncall", value="alice", confidence=1.0)
    commit = engine.commit(agent_id="human-ops", facts=[fact], strict_evidence=True)
    assert commit.status == "VALIDATED"
    assert engine.blame("oncall")["value"] == "alice"  # type: ignore[index]


# --------------------------------------------------------------------------- firewall rule 2


def test_firewall_blocks_low_confidence_overwrite(engine: AgentLedgerEngine) -> None:
    high = _tool_fact(
        engine,
        namespace="crm",
        entity_key="user.tier",
        value="gold",
        raw_text="tier=gold from billing export",
        confidence=0.95,
    )
    engine.commit(agent_id="agent-billing", facts=[high], timestamp=1_000_000.0)

    low = _tool_fact(
        engine,
        namespace="crm",
        entity_key="user.tier",
        value="silver",  # different value
        raw_text="tier=silver from stale cache",
        confidence=0.40,  # lower than active decayed confidence (~0.95)
    )
    with pytest.raises(ProvenanceFirewallError, match="LOW_CONFIDENCE_OVERWRITE"):
        engine.commit(agent_id="agent-cache", facts=[low], timestamp=1_000_100.0)

    blamed = engine.blame("user.tier", now=1_000_100.0)
    assert blamed is not None
    assert blamed["value"] == "gold"
    assert blamed["agent_id"] == "agent-billing"


def test_equal_or_higher_confidence_overwrite_allowed(engine: AgentLedgerEngine) -> None:
    first = _tool_fact(
        engine,
        namespace="crm",
        entity_key="user.tier",
        value="gold",
        raw_text="tier=gold",
        confidence=0.7,
    )
    engine.commit(agent_id="a1", facts=[first], timestamp=1_000_000.0)

    second = _tool_fact(
        engine,
        namespace="crm",
        entity_key="user.tier",
        value="platinum",
        raw_text="tier=platinum audited",
        confidence=0.85,
    )
    c2 = engine.commit(agent_id="a2", facts=[second], timestamp=1_000_200.0)
    assert c2.status == "VALIDATED"
    assert engine.blame("user.tier", now=1_000_200.0)["value"] == "platinum"  # type: ignore[index]


# --------------------------------------------------------------------------- confidence decay


def test_confidence_decay_math() -> None:
    fact = MemoryFact(
        namespace="n",
        entity_key="k",
        value=1,
        initial_confidence=1.0,
        half_life_hours=10.0,
        evidence=EvidenceAnchor(
            source_type=SourceType.HUMAN_VERIFIED,
            source_uri="human://t",
            raw_artifact_sha256="0" * 64,
        ),
    )
    t0 = 0.0
    # After one half-life (10 hours) → ~0.5
    ten_hours = 10.0 * 3600.0
    decayed = fact.current_confidence(t0, now=ten_hours)
    assert decayed == pytest.approx(0.5, rel=1e-9)

    # After two half-lives → ~0.25
    twenty_hours = 20.0 * 3600.0
    decayed2 = fact.current_confidence(t0, now=twenty_hours)
    assert decayed2 == pytest.approx(0.25, rel=1e-9)

    # Manual formula check
    elapsed_hours = 5.0
    expected = 1.0 * math.exp(-(math.log(2) / 10.0) * elapsed_hours)
    assert fact.current_confidence(t0, now=elapsed_hours * 3600.0) == pytest.approx(expected)


def test_read_facts_filters_by_decayed_confidence(engine: AgentLedgerEngine) -> None:
    fact = _tool_fact(
        engine,
        namespace="tmp",
        entity_key="ephemeral",
        value="x",
        raw_text="ephemeral signal",
        confidence=0.8,
        half_life_hours=1.0,
    )
    engine.commit(agent_id="a", facts=[fact], timestamp=0.0)

    # Immediately readable
    facts_now, _ = engine.read_facts(min_confidence=0.4, now=0.0)
    assert len(facts_now) == 1

    # After many half-lives, decayed below threshold
    far_future = 10.0 * 3600.0  # 10 hours, half-life 1h → conf ≈ 0.8/1024
    facts_later, _ = engine.read_facts(min_confidence=0.4, now=far_future)
    assert facts_later == []


# --------------------------------------------------------------------------- 4-agent cascade


def test_four_agent_causal_cascade_quarantine(engine: AgentLedgerEngine) -> None:
    """Agent1 → Agent2 → Agent3 → Agent4; revert Agent1 quarantines 2–4, not unrelated."""
    t = 1_700_000_000.0

    f1 = _tool_fact(
        engine,
        namespace="research",
        entity_key="claim.root",
        value="earth_is_round",
        raw_text="sensor: curvature detected",
        confidence=0.95,
    )
    c1 = engine.commit(agent_id="agent-1", facts=[f1], causal_read_hashes=[], timestamp=t)

    # Each agent records only the immediate upstream commit it read (clean A1→A2→A3→A4 chain).
    _, reads1 = engine.read_facts(namespace="research", min_confidence=0.1, now=t + 1)
    assert reads1 == [c1.commit_hash]
    f2 = _human_fact(
        namespace="research",
        entity_key="claim.derived_a",
        value="ships_hull_first",
        confidence=0.9,
    )
    c2 = engine.commit(
        agent_id="agent-2",
        facts=[f2],
        causal_read_hashes=[c1.commit_hash],
        timestamp=t + 10,
    )

    f3 = _human_fact(
        namespace="research",
        entity_key="claim.derived_b",
        value="horizon_drop",
        confidence=0.85,
    )
    c3 = engine.commit(
        agent_id="agent-3",
        facts=[f3],
        causal_read_hashes=[c2.commit_hash],
        timestamp=t + 20,
    )

    f4 = _human_fact(
        namespace="research",
        entity_key="claim.derived_c",
        value="satellite_photos",
        confidence=0.8,
    )
    c4 = engine.commit(
        agent_id="agent-4",
        facts=[f4],
        causal_read_hashes=[c3.commit_hash],
        timestamp=t + 30,
    )

    # Unrelated commit that does NOT causally read the chain
    unrelated = _tool_fact(
        engine,
        namespace="ops",
        entity_key="deploy.channel",
        value="stable",
        raw_text="deploy channel=stable",
        confidence=0.99,
    )
    c_unrelated = engine.commit(
        agent_id="agent-ops",
        facts=[unrelated],
        causal_read_hashes=[],
        timestamp=t + 40,
    )

    assert c2.causal_read_hashes == [c1.commit_hash]
    assert c3.causal_read_hashes == [c2.commit_hash]
    assert c4.causal_read_hashes == [c3.commit_hash]

    quarantined = engine.revert_cascade(c1.commit_hash)

    assert quarantined == [
        c1.commit_hash,
        c2.commit_hash,
        c3.commit_hash,
        c4.commit_hash,
    ]

    assert engine.get_commit(c1.commit_hash).status == "QUARANTINED"  # type: ignore[union-attr]
    assert engine.get_commit(c2.commit_hash).status == "QUARANTINED"  # type: ignore[union-attr]
    assert engine.get_commit(c3.commit_hash).status == "QUARANTINED"  # type: ignore[union-attr]
    assert engine.get_commit(c4.commit_hash).status == "QUARANTINED"  # type: ignore[union-attr]

    # Unrelated remains VALIDATED and readable
    assert engine.get_commit(c_unrelated.commit_hash).status == "VALIDATED"  # type: ignore[union-attr]
    blamed = engine.blame("deploy.channel", now=t + 50)
    assert blamed is not None
    assert blamed["value"] == "stable"
    assert blamed["commit_hash"] == c_unrelated.commit_hash

    # Chain facts gone from active reads
    research_facts, _ = engine.read_facts(namespace="research", min_confidence=0.0, now=t + 50)
    assert research_facts == []
    assert engine.blame("claim.root", now=t + 50) is None


def test_revert_unknown_commit_raises(engine: AgentLedgerEngine) -> None:
    with pytest.raises(KeyError):
        engine.revert_cascade("0" * 64)


# --------------------------------------------------------------------------- MCP tools


@pytest.fixture
def mcp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "mcp_ledger.db"
    monkeypatch.setenv("AGENTLEDGER_DB", str(db))
    return db


def test_mcp_register_read_commit_blame_revert(mcp_db: Path) -> None:
    from agentledger import mcp_server as ms

    raw = "mcp scrape: prospect::tier=Growth"
    reg = ms.ledger_register_evidence(raw)
    assert reg["ok"] is True
    assert len(reg["sha256"]) == 64

    blocked = ms.ledger_commit(
        agent_id="bot-researcher",
        namespace="prospect",
        entity_key="tier",
        value="Enterprise",
        evidence_sha256="c" * 64,
        source_uri="tool://mcp",
        excerpt="fake",
    )
    assert blocked["ok"] is False
    assert "UNVERIFIED_RECEIPT" in blocked["detail"]

    committed = ms.ledger_commit(
        agent_id="bot-researcher",
        namespace="prospect",
        entity_key="tier",
        value="Growth",
        evidence_sha256=reg["sha256"],
        source_uri="tool://mcp",
        excerpt=raw,
        initial_confidence=0.93,
    )
    assert committed["ok"] is True
    root_hash = committed["commit"]["commit_hash"]

    read = ms.ledger_read(namespace="prospect", min_confidence=0.4)
    assert read["ok"] is True
    assert len(read["facts"]) == 1
    assert root_hash in read["causal_read_hashes"]

    derived = ms.ledger_commit(
        agent_id="bot-pricer",
        namespace="prospect",
        entity_key="quote_usd",
        value="42000",
        evidence_sha256=reg["sha256"],
        source_uri="tool://mcp/pricer",
        excerpt="derived quote",
        causal_read_hashes=read["causal_read_hashes"],
        initial_confidence=0.9,
    )
    assert derived["ok"] is True

    # Unrelated commit
    raw2 = "mcp scrape: other::tier=Starter"
    reg2 = ms.ledger_register_evidence(raw2)
    other = ms.ledger_commit(
        agent_id="bot-researcher",
        namespace="other",
        entity_key="tier",
        value="Starter",
        evidence_sha256=reg2["sha256"],
        source_uri="tool://mcp",
        excerpt=raw2,
    )
    assert other["ok"] is True

    blamed = ms.ledger_blame("prospect::tier")
    assert blamed["ok"] is True
    assert blamed["blame"]["value"] == "Growth"
    assert blamed["blame"]["agent_id"] == "bot-researcher"

    reverted = ms.ledger_revert_cascade(root_hash[:12])
    assert reverted["ok"] is True
    assert root_hash in reverted["quarantined_commit_hashes"]
    assert derived["commit"]["commit_hash"] in reverted["quarantined_commit_hashes"]
    assert other["commit"]["commit_hash"] not in reverted["quarantined_commit_hashes"]

    after = ms.ledger_read(namespace="prospect", min_confidence=0.0)
    assert after["facts"] == []
    still = ms.ledger_blame("other::tier")
    assert still["ok"] is True
    assert still["blame"]["value"] == "Starter"


def test_mcp_server_name_and_tool_exports() -> None:
    from agentledger import mcp_server as ms

    assert ms.mcp.name == "AgentLedger"
    for name in (
        "ledger_register_evidence",
        "ledger_read",
        "ledger_commit",
        "ledger_blame",
        "ledger_revert_cascade",
    ):
        assert callable(getattr(ms, name))
