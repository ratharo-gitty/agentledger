"""Pydantic v2 schemas for AgentLedger Phase 1."""

from __future__ import annotations

import hashlib
import json
import math
import time
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class SourceType(str, Enum):
    TOOL_STDOUT = "TOOL_STDOUT"
    HTTP_RESPONSE = "HTTP_RESPONSE"
    FILE_SPAN = "FILE_SPAN"
    HUMAN_VERIFIED = "HUMAN_VERIFIED"


class EvidenceAnchor(BaseModel):
    """Receipt linking a fact to a registered runtime artifact (or human verification)."""

    source_type: SourceType
    source_uri: str = Field(..., min_length=1)
    raw_artifact_sha256: str = Field(..., min_length=64, max_length=64)
    excerpt: str = ""

    @field_validator("raw_artifact_sha256")
    @classmethod
    def _hex_sha256(cls, value: str) -> str:
        value = value.lower()
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("raw_artifact_sha256 must be a 64-char lowercase hex digest")
        return value


class MemoryFact(BaseModel):
    """A single namespaced fact with exponential confidence decay."""

    namespace: str = Field(..., min_length=1)
    entity_key: str = Field(..., min_length=1)
    value: Any
    initial_confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    half_life_hours: float = Field(default=720.0, gt=0.0)
    evidence: EvidenceAnchor

    def current_confidence(
        self,
        commit_timestamp: float,
        now: float | None = None,
    ) -> float:
        """Exponential decay: C0 * exp(-(ln(2)/half_life_hours) * elapsed_hours)."""
        ref = time.time() if now is None else now
        elapsed_hours = max(0.0, (ref - commit_timestamp) / 3600.0)
        decay = math.exp(-(math.log(2) / self.half_life_hours) * elapsed_hours)
        return max(0.0, min(1.0, self.initial_confidence * decay))


class MemoryCommit(BaseModel):
    """Deterministic commit bundling facts and causal read provenance."""

    commit_hash: str = Field(..., min_length=64, max_length=64)
    parent_hash: str | None = None
    branch: str = "main"
    agent_id: str = Field(..., min_length=1)
    timestamp: float
    causal_read_hashes: list[str] = Field(default_factory=list)
    facts: list[MemoryFact] = Field(default_factory=list)
    status: Literal["VALIDATED", "QUARANTINED"] = "VALIDATED"

    @field_validator("commit_hash")
    @classmethod
    def _hex_commit(cls, value: str) -> str:
        value = value.lower()
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("commit_hash must be a 64-char lowercase hex digest")
        return value

    @staticmethod
    def compute_hash(
        *,
        parent_hash: str | None,
        branch: str,
        agent_id: str,
        timestamp: float,
        causal_read_hashes: list[str],
        facts: list[MemoryFact],
    ) -> str:
        """Deterministic SHA-256 over canonical commit payload (excludes status/hash)."""
        payload = {
            "parent_hash": parent_hash,
            "branch": branch,
            "agent_id": agent_id,
            "timestamp": timestamp,
            "causal_read_hashes": list(causal_read_hashes),
            "facts": [f.model_dump(mode="json") for f in facts],
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()
