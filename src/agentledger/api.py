"""High-level API: ``ledger.agent``, ``ledger.get``/``set``, ``@ledger.watch``."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, ParamSpec, TypeVar

from agentledger.engine import AgentLedgerEngine
from agentledger.models import EvidenceAnchor, MemoryCommit, MemoryFact, SourceType

P = ParamSpec("P")
R = TypeVar("R")


@dataclass
class _AgentSession:
    agent_id: str
    causal_reads: list[str] = field(default_factory=list)


_session: ContextVar[_AgentSession | None] = ContextVar("agentledger_session", default=None)


def _split_key(key: str, namespace: str) -> tuple[str, str]:
    """Support ``namespace::entity`` keys or separate namespace + key."""
    if "::" in key:
        ns, entity = key.split("::", 1)
        if not ns or not entity:
            raise ValueError(f"invalid compound key: {key!r}")
        return ns, entity
    return namespace, key


class Ledger:
    """Facade over :class:`AgentLedgerEngine` with causal context tracking."""

    def __init__(self) -> None:
        self._engine: AgentLedgerEngine | None = None
        self._db_path: str = ".agentledger/ledger.db"
        self._lock = threading.RLock()

    def configure(self, db_path: str = ".agentledger/ledger.db") -> None:
        """Point the global ledger at a new database (e.g. ``:memory:`` for tests)."""
        with self._lock:
            if self._engine is not None:
                self._engine.close()
            self._engine = None
            self._db_path = db_path

    @property
    def engine(self) -> AgentLedgerEngine:
        with self._lock:
            if self._engine is None:
                self._engine = AgentLedgerEngine(self._db_path)
            return self._engine

    def _active(self) -> _AgentSession | None:
        return _session.get()

    @contextmanager
    def agent(self, agent_id: str) -> Iterator[str]:
        """Bind an agent session; ``get``/``set`` collect and attach causal hashes."""
        if not agent_id:
            raise ValueError("agent_id must be non-empty")
        token = _session.set(_AgentSession(agent_id=agent_id))
        try:
            yield agent_id
        finally:
            _session.reset(token)

    def get(
        self,
        key: str,
        namespace: str = "default",
        min_confidence: float = 0.4,
    ) -> Any:
        """Read an active fact value and record its commit hash for downstream writes."""
        ns, entity = _split_key(key, namespace)
        facts, _ = self.engine.read_facts(namespace=ns, min_confidence=min_confidence)
        hit = next((f for f in facts if f["entity_key"] == entity), None)
        if hit is None:
            # Fallback: blame may see namespaced or bare keys below confidence filter edge.
            blamed = self.engine.blame(f"{ns}::{entity}")
            if blamed is None or blamed["current_confidence"] < min_confidence:
                return None
            hit = blamed

        commit_hash = hit["commit_hash"]
        session = self._active()
        if session is not None and commit_hash not in session.causal_reads:
            session.causal_reads.append(commit_hash)
        return hit["value"]

    def set(
        self,
        key: str,
        value: Any,
        raw_evidence: str | None = None,
        source_uri: str = "internal://runtime",
        namespace: str = "default",
        *,
        initial_confidence: float = 0.9,
        half_life_hours: float = 720.0,
    ) -> MemoryCommit:
        """Commit a fact, hashing evidence and attaching the active session's causal reads."""
        ns, entity = _split_key(key, namespace)
        session = self._active()
        agent_id = session.agent_id if session is not None else "anonymous"
        causal = list(session.causal_reads) if session is not None else []

        if raw_evidence is not None:
            digest = self.engine.register_artifact(raw_evidence)
            evidence = EvidenceAnchor(
                source_type=SourceType.TOOL_STDOUT,
                source_uri=source_uri,
                raw_artifact_sha256=digest,
                excerpt=raw_evidence[:120],
            )
        else:
            payload = str(value)
            digest = self.engine.hash_text(payload)
            evidence = EvidenceAnchor(
                source_type=SourceType.HUMAN_VERIFIED,
                source_uri=source_uri,
                raw_artifact_sha256=digest,
                excerpt=payload[:120],
            )

        fact = MemoryFact(
            namespace=ns,
            entity_key=entity,
            value=value,
            initial_confidence=initial_confidence,
            half_life_hours=half_life_hours,
            evidence=evidence,
        )
        return self.engine.commit(
            agent_id=agent_id,
            facts=[fact],
            causal_read_hashes=causal,
            strict_evidence=True,
        )

    def watch(
        self,
        key: str,
        namespace: str = "default",
        source_uri: str = "tool://function",
        *,
        initial_confidence: float = 0.9,
    ) -> Callable[[Callable[P, R]], Callable[P, R]]:
        """Decorator: hash the function return value as evidence and commit under ``key``."""

        def decorator(func: Callable[P, R]) -> Callable[P, R]:
            @wraps(func)
            def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                result = func(*args, **kwargs)
                raw = result if isinstance(result, str) else str(result)
                uri = source_uri
                if uri == "tool://function":
                    uri = f"tool://{func.__module__}.{func.__qualname__}"
                self.set(
                    key=key,
                    value=raw,
                    raw_evidence=raw,
                    source_uri=uri,
                    namespace=namespace,
                    initial_confidence=initial_confidence,
                )
                return result

            return wrapper

        return decorator

    def revert(self, commit_hash: str) -> list[str]:
        """BFS-quarantine ``commit_hash`` (full hash or unique prefix) and dependents."""
        engine = self.engine
        resolved = commit_hash
        if len(commit_hash) < 64:
            resolved = engine.resolve_commit_prefix(commit_hash).commit_hash
        return engine.revert_cascade(resolved)

    def blame(self, key: str, namespace: str = "default") -> dict[str, Any] | None:
        """Blame for a bare or ``namespace::entity`` key."""
        ns, entity = _split_key(key, namespace)
        return self.engine.blame(f"{ns}::{entity}")


ledger = Ledger()
