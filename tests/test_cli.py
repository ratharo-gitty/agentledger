"""Golden coverage for the Markdown audit export command."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from agentledger.cli import app
from agentledger.engine import AgentLedgerEngine
from agentledger.models import EvidenceAnchor, MemoryFact, SourceType


GOLDEN = Path(__file__).parent / "golden" / "audit_seed.md"
runner = CliRunner()


def _seed_audit_ledger(db_path: Path) -> None:
    with AgentLedgerEngine(str(db_path)) as engine:
        raw = "seed audit: northwind::tier=Professional"
        digest = engine.register_artifact(raw)
        root = MemoryFact(
            namespace="northwind",
            entity_key="tier",
            value="Professional",
            initial_confidence=0.94,
            evidence=EvidenceAnchor(
                source_type=SourceType.TOOL_STDOUT,
                source_uri="tool://seed/audit",
                raw_artifact_sha256=digest,
                excerpt=raw,
            ),
        )
        root_commit = engine.commit(
            agent_id="seed-researcher",
            facts=[root],
            timestamp=1_700_000_000.0,
        )

        derived = MemoryFact(
            namespace="northwind",
            entity_key="quote_usd",
            value=48_000,
            initial_confidence=0.9,
            evidence=EvidenceAnchor(
                source_type=SourceType.HUMAN_VERIFIED,
                source_uri="human://seed/audit",
                raw_artifact_sha256="0" * 64,
                excerpt="Seed audit quote",
            ),
        )
        derived_commit = engine.commit(
            agent_id="seed-pricer",
            facts=[derived],
            causal_read_hashes=[root_commit.commit_hash],
            timestamp=1_700_000_060.0,
        )

        unrelated = MemoryFact(
            namespace="contoso",
            entity_key="tier",
            value="Starter",
            initial_confidence=0.91,
            evidence=EvidenceAnchor(
                source_type=SourceType.HUMAN_VERIFIED,
                source_uri="human://seed/audit",
                raw_artifact_sha256="0" * 64,
                excerpt="Unrelated validated fact",
            ),
        )
        engine.commit(
            agent_id="seed-ops",
            facts=[unrelated],
            timestamp=1_700_000_120.0,
        )
        engine.revert_cascade(derived_commit.commit_hash)


def test_export_matches_seeded_audit_golden(tmp_path: Path) -> None:
    db_path = tmp_path / "seed.db"
    _seed_audit_ledger(db_path)

    result = runner.invoke(app, ["export", "--db", str(db_path)])

    assert result.exit_code == 0, result.stdout
    assert result.stdout == GOLDEN.read_text(encoding="utf-8")
    assert "[QUARANTINED]" in result.stdout
    assert "Evidence SHA-256" in result.stdout


def test_export_can_write_markdown_file(tmp_path: Path) -> None:
    db_path = tmp_path / "seed.db"
    output_path = tmp_path / "reports" / "audit.md"
    _seed_audit_ledger(db_path)

    result = runner.invoke(
        app,
        ["export", "--db", str(db_path), "--output", str(output_path)],
    )

    assert result.exit_code == 0, result.stdout
    assert output_path.read_text(encoding="utf-8") == GOLDEN.read_text(encoding="utf-8")
