"""AgentLedger engine: artifact registry, Provenance Firewall, BFS cascade quarantine."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from collections import deque
from pathlib import Path
from typing import Any

from agentledger.models import MemoryCommit, MemoryFact, SourceType


class ProvenanceFirewallError(Exception):
    """Raised when a commit violates Provenance Firewall rules."""


class AgentLedgerEngine:
    """SQLite-backed multi-agent ledger with evidence receipts and causal quarantine."""

    def __init__(self, db_path: str = ".agentledger/ledger.db") -> None:
        self.db_path = db_path
        if db_path == ":memory:":
            self._conn: sqlite3.Connection | None = sqlite3.connect(
                ":memory:", check_same_thread=False
            )
            self._conn.row_factory = sqlite3.Row
            self._init_schema(self._conn)
        else:
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = None
            with self._connect() as conn:
                self._init_schema(conn)

    # ------------------------------------------------------------------ internals

    def _connect(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _close_if_file(self, conn: sqlite3.Connection) -> None:
        if self._conn is None:
            conn.close()

    @staticmethod
    def _init_schema(conn: sqlite3.Connection) -> None:
        # Drop pre-Phase-1 schemas that used commit_id / facts tables.
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='commits'"
        ).fetchone()
        if row and row[0] and "commit_hash" not in row[0]:
            conn.executescript(
                """
                DROP TABLE IF EXISTS facts;
                DROP TABLE IF EXISTS commits;
                DROP TABLE IF EXISTS branch_pointers;
                DROP TABLE IF EXISTS artifacts;
                """
            )

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS artifacts (
                sha256 TEXT PRIMARY KEY,
                raw_text TEXT NOT NULL,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS commits (
                commit_hash TEXT PRIMARY KEY,
                parent_hash TEXT,
                branch TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                causal_read_hashes_json TEXT NOT NULL,
                facts_json TEXT NOT NULL,
                status TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS branch_pointers (
                branch TEXT PRIMARY KEY,
                head_hash TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_commits_branch_status
                ON commits(branch, status);
            CREATE INDEX IF NOT EXISTS idx_commits_timestamp
                ON commits(timestamp);
            """
        )
        conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> AgentLedgerEngine:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ------------------------------------------------------------------ artifacts

    @staticmethod
    def hash_text(raw_text: str) -> str:
        return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

    def register_artifact(self, raw_text: str) -> str:
        """Compute SHA-256 of raw tool/scrape output, persist it, return the hash."""
        digest = self.hash_text(raw_text)
        now = time.time()
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO artifacts (sha256, raw_text, created_at)
                VALUES (?, ?, ?)
                """,
                (digest, raw_text, now),
            )
            conn.commit()
        finally:
            self._close_if_file(conn)
        return digest

    def artifact_exists(self, sha256: str) -> bool:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT 1 FROM artifacts WHERE sha256 = ?",
                (sha256.lower(),),
            ).fetchone()
            return row is not None
        finally:
            self._close_if_file(conn)

    # ------------------------------------------------------------------ reads

    def get_head(self, branch: str = "main") -> str | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT head_hash FROM branch_pointers WHERE branch = ?",
                (branch,),
            ).fetchone()
            return row["head_hash"] if row else None
        finally:
            self._close_if_file(conn)

    def _load_validated_commits(self, branch: str = "main") -> list[MemoryCommit]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT * FROM commits
                WHERE branch = ? AND status = 'VALIDATED'
                ORDER BY timestamp ASC, commit_hash ASC
                """,
                (branch,),
            ).fetchall()
            return [self._row_to_commit(r) for r in rows]
        finally:
            self._close_if_file(conn)

    @staticmethod
    def _fact_slot(namespace: str, entity_key: str) -> str:
        return f"{namespace}::{entity_key}"

    def _active_fact_index(
        self,
        branch: str = "main",
        *,
        now: float | None = None,
    ) -> dict[str, tuple[MemoryFact, MemoryCommit, float]]:
        """Map ``namespace::entity_key`` → (fact, commit, decayed_confidence)."""
        ref = time.time() if now is None else now
        index: dict[str, tuple[MemoryFact, MemoryCommit, float]] = {}
        for commit in self._load_validated_commits(branch):
            for fact in commit.facts:
                conf = fact.current_confidence(commit.timestamp, now=ref)
                slot = self._fact_slot(fact.namespace, fact.entity_key)
                # Latest write by timestamp wins for that namespaced slot.
                prev = index.get(slot)
                if prev is None or commit.timestamp >= prev[1].timestamp:
                    index[slot] = (fact, commit, conf)
        return index

    def read_facts(
        self,
        namespace: str | None = None,
        min_confidence: float = 0.4,
        *,
        now: float | None = None,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Return active VALIDATED facts on main meeting min_confidence + causal hashes."""
        ref = time.time() if now is None else now
        active = self._active_fact_index("main", now=ref)
        results: list[dict[str, Any]] = []
        read_hashes: list[str] = []
        seen_hashes: set[str] = set()

        for _slot, (fact, commit, conf) in sorted(active.items()):
            if namespace is not None and fact.namespace != namespace:
                continue
            if conf < min_confidence:
                continue
            results.append(
                {
                    "namespace": fact.namespace,
                    "entity_key": fact.entity_key,
                    "value": fact.value,
                    "initial_confidence": fact.initial_confidence,
                    "current_confidence": conf,
                    "half_life_hours": fact.half_life_hours,
                    "evidence": fact.evidence.model_dump(mode="json"),
                    "commit_hash": commit.commit_hash,
                    "agent_id": commit.agent_id,
                    "timestamp": commit.timestamp,
                }
            )
            if commit.commit_hash not in seen_hashes:
                seen_hashes.add(commit.commit_hash)
                read_hashes.append(commit.commit_hash)

        return results, read_hashes

    # ------------------------------------------------------------------ commit

    def commit(
        self,
        agent_id: str,
        facts: list[MemoryFact],
        causal_read_hashes: list[str] | None = None,
        branch: str = "main",
        strict_evidence: bool = True,
        *,
        timestamp: float | None = None,
    ) -> MemoryCommit:
        if not facts:
            raise ValueError("commit requires at least one fact")

        causal = list(causal_read_hashes or [])
        ts = time.time() if timestamp is None else timestamp
        parent_hash = self.get_head(branch)

        # FIREWALL RULE 1 — artifact must exist unless human-verified.
        if strict_evidence:
            for fact in facts:
                ev = fact.evidence
                if ev.source_type == SourceType.HUMAN_VERIFIED:
                    continue
                if not self.artifact_exists(ev.raw_artifact_sha256):
                    raise ProvenanceFirewallError(
                        "UNVERIFIED_RECEIPT: "
                        f"raw_artifact_sha256={ev.raw_artifact_sha256} "
                        f"for entity_key={fact.entity_key!r} is not registered"
                    )

        # FIREWALL RULE 2 — block low-confidence overwrite of stronger active fact.
        active = self._active_fact_index(branch, now=ts)
        for fact in facts:
            slot = self._fact_slot(fact.namespace, fact.entity_key)
            existing = active.get(slot)
            if existing is None:
                continue
            old_fact, _old_commit, old_conf = existing
            if old_fact.value != fact.value and old_conf > fact.initial_confidence:
                raise ProvenanceFirewallError(
                    "LOW_CONFIDENCE_OVERWRITE: "
                    f"entity_key={fact.entity_key!r} has active confidence={old_conf:.6f} "
                    f"with value={old_fact.value!r}; refused overwrite with "
                    f"initial_confidence={fact.initial_confidence} value={fact.value!r}"
                )

        commit_hash = MemoryCommit.compute_hash(
            parent_hash=parent_hash,
            branch=branch,
            agent_id=agent_id,
            timestamp=ts,
            causal_read_hashes=causal,
            facts=facts,
        )
        memory_commit = MemoryCommit(
            commit_hash=commit_hash,
            parent_hash=parent_hash,
            branch=branch,
            agent_id=agent_id,
            timestamp=ts,
            causal_read_hashes=causal,
            facts=facts,
            status="VALIDATED",
        )

        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO commits (
                    commit_hash, parent_hash, branch, agent_id, timestamp,
                    causal_read_hashes_json, facts_json, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_commit.commit_hash,
                    memory_commit.parent_hash,
                    memory_commit.branch,
                    memory_commit.agent_id,
                    memory_commit.timestamp,
                    json.dumps(memory_commit.causal_read_hashes),
                    json.dumps([f.model_dump(mode="json") for f in memory_commit.facts]),
                    memory_commit.status,
                ),
            )
            conn.execute(
                """
                INSERT INTO branch_pointers (branch, head_hash)
                VALUES (?, ?)
                ON CONFLICT(branch) DO UPDATE SET head_hash = excluded.head_hash
                """,
                (branch, memory_commit.commit_hash),
            )
            conn.commit()
        finally:
            self._close_if_file(conn)

        return memory_commit

    # ------------------------------------------------------------------ blame

    def blame(self, entity_key: str, *, now: float | None = None) -> dict[str, Any] | None:
        """Return the active fact, writer agent, commit hash, confidence, and evidence.

        ``entity_key`` may be bare (``tier``) or namespaced (``acme_corp::tier``).
        Bare keys resolve to the newest matching active fact across namespaces.
        """
        active = self._active_fact_index("main", now=now)
        if "::" in entity_key:
            hit = active.get(entity_key)
        else:
            candidates = [item for item in active.values() if item[0].entity_key == entity_key]
            hit = max(candidates, key=lambda x: x[1].timestamp) if candidates else None
        if hit is None:
            return None
        fact, commit, conf = hit
        return {
            "namespace": fact.namespace,
            "entity_key": fact.entity_key,
            "value": fact.value,
            "agent_id": commit.agent_id,
            "commit_hash": commit.commit_hash,
            "timestamp": commit.timestamp,
            "current_confidence": conf,
            "initial_confidence": fact.initial_confidence,
            "evidence": fact.evidence.model_dump(mode="json"),
        }

    # ----------------------------------------------------------- cascade revert

    def revert_cascade(self, bad_commit_hash: str) -> list[str]:
        """BFS-quarantine ``bad_commit_hash`` and every downstream causal dependent.

        A commit D depends on C when ``C`` appears in ``D.causal_read_hashes``
        (directly or via previously discovered dependents).
        """
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT commit_hash, causal_read_hashes_json, status, timestamp FROM commits"
            ).fetchall()
        finally:
            self._close_if_file(conn)

        if not any(r["commit_hash"] == bad_commit_hash for r in rows):
            raise KeyError(f"unknown commit_hash: {bad_commit_hash}")

        # parent_hash_in_causal -> dependent commit hashes
        dependents: dict[str, set[str]] = {r["commit_hash"]: set() for r in rows}
        for row in rows:
            child = row["commit_hash"]
            parents = json.loads(row["causal_read_hashes_json"])
            for parent in parents:
                if parent in dependents:
                    dependents[parent].add(child)
                else:
                    # External/unknown parent still seeds adjacency for known children.
                    dependents.setdefault(parent, set()).add(child)

        quarantined: list[str] = []
        seen: set[str] = set()
        queue: deque[str] = deque([bad_commit_hash])
        while queue:
            current = queue.popleft()
            if current in seen:
                continue
            seen.add(current)
            # Only record hashes that exist in our ledger.
            if any(r["commit_hash"] == current for r in rows):
                quarantined.append(current)
            for child in sorted(dependents.get(current, ())):
                if child not in seen:
                    queue.append(child)

        conn = self._connect()
        try:
            for ch in quarantined:
                conn.execute(
                    "UPDATE commits SET status = 'QUARANTINED' WHERE commit_hash = ?",
                    (ch,),
                )
            # Rewind branch heads if they pointed at a quarantined commit.
            branch_rows = conn.execute("SELECT branch, head_hash FROM branch_pointers").fetchall()
            for brow in branch_rows:
                if brow["head_hash"] not in set(quarantined):
                    continue
                # Walk parent chain to nearest VALIDATED ancestor.
                head = brow["head_hash"]
                new_head: str | None = None
                while head is not None:
                    crow = conn.execute(
                        "SELECT parent_hash, status FROM commits WHERE commit_hash = ?",
                        (head,),
                    ).fetchone()
                    if crow is None:
                        break
                    parent = crow["parent_hash"]
                    if parent is None:
                        new_head = None
                        break
                    prow = conn.execute(
                        "SELECT status FROM commits WHERE commit_hash = ?",
                        (parent,),
                    ).fetchone()
                    if prow and prow["status"] == "VALIDATED":
                        new_head = parent
                        break
                    head = parent
                conn.execute(
                    "UPDATE branch_pointers SET head_hash = ? WHERE branch = ?",
                    (new_head, brow["branch"]),
                )
            conn.commit()
        finally:
            self._close_if_file(conn)

        return quarantined

    def get_commit(self, commit_hash: str) -> MemoryCommit | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM commits WHERE commit_hash = ?",
                (commit_hash,),
            ).fetchone()
            return self._row_to_commit(row) if row else None
        finally:
            self._close_if_file(conn)

    def list_commits(
        self,
        *,
        branch: str | None = None,
        include_quarantined: bool = True,
    ) -> list[MemoryCommit]:
        """Return commits newest-first (optionally filtered by branch/status)."""
        conn = self._connect()
        try:
            clauses: list[str] = []
            params: list[Any] = []
            if branch is not None:
                clauses.append("branch = ?")
                params.append(branch)
            if not include_quarantined:
                clauses.append("status = 'VALIDATED'")
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            rows = conn.execute(
                f"""
                SELECT * FROM commits
                {where}
                ORDER BY timestamp DESC, commit_hash DESC
                """,
                params,
            ).fetchall()
            return [self._row_to_commit(r) for r in rows]
        finally:
            self._close_if_file(conn)

    def resolve_commit_prefix(self, prefix: str) -> MemoryCommit:
        """Resolve a unique commit by hash prefix (raises KeyError / ValueError)."""
        if not prefix:
            raise ValueError("commit hash prefix must be non-empty")
        needle = prefix.lower()
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM commits WHERE commit_hash LIKE ?",
                (f"{needle}%",),
            ).fetchall()
        finally:
            self._close_if_file(conn)
        if not rows:
            raise KeyError(f"no commit matches prefix {prefix!r}")
        if len(rows) > 1:
            matches = ", ".join(r["commit_hash"][:12] for r in rows[:5])
            raise ValueError(
                f"ambiguous commit prefix {prefix!r} matches {len(rows)} commits: {matches}"
            )
        return self._row_to_commit(rows[0])

    @staticmethod
    def _row_to_commit(row: sqlite3.Row) -> MemoryCommit:
        facts_raw = json.loads(row["facts_json"])
        facts = [MemoryFact.model_validate(f) for f in facts_raw]
        return MemoryCommit.model_validate(
            {
                "commit_hash": row["commit_hash"],
                "parent_hash": row["parent_hash"],
                "branch": row["branch"],
                "agent_id": row["agent_id"],
                "timestamp": row["timestamp"],
                "causal_read_hashes": json.loads(row["causal_read_hashes_json"]),
                "facts": facts,
                "status": row["status"],
            }
        )


# Backward-compatible alias used by earlier package exports / CLI.
LedgerEngine = AgentLedgerEngine
