# AgentLedger Audit Export

_Commits: 3 · Quarantined commits are marked explicitly._

## Commit `2228541ab2b60d51095705e0786f83e57e915c7889c3f54616800f6775e11931` [VALIDATED]

> **Status:** `VALIDATED`

| Field | Value |
| --- | --- |
| Agent | `seed-ops` |
| Timestamp | `1700000120.000000 (2023-11-14T22:15:20Z)` |
| Branch | `main` |
| Parent commit | `214576e211cae19740b1c07694216c67e96d6fd4874f259f4947066c38bcf35b` |
| Causal parents | — |

### Fact payload

#### `contoso::tier`

```json
{
  "entity_key": "tier",
  "evidence": {
    "excerpt": "Unrelated validated fact",
    "raw_artifact_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
    "source_type": "HUMAN_VERIFIED",
    "source_uri": "human://seed/audit"
  },
  "half_life_hours": 720.0,
  "initial_confidence": 0.91,
  "namespace": "contoso",
  "value": "Starter"
}
```

- **Evidence SHA-256:** `0000000000000000000000000000000000000000000000000000000000000000`
- **Evidence source:** `HUMAN_VERIFIED` — `human://seed/audit`
- **Evidence excerpt:** Unrelated validated fact

---

## Commit `214576e211cae19740b1c07694216c67e96d6fd4874f259f4947066c38bcf35b` [QUARANTINED]

> **Status:** `QUARANTINED`
> **QUARANTINED:** excluded from active memory until restored.

| Field | Value |
| --- | --- |
| Agent | `seed-pricer` |
| Timestamp | `1700000060.000000 (2023-11-14T22:14:20Z)` |
| Branch | `main` |
| Parent commit | `ccd3557f87bf1d1fb92fd94cb00314a2b067cdf5fdc48b314de1d3f9b79f0806` |
| Causal parents | `ccd3557f87bf1d1fb92fd94cb00314a2b067cdf5fdc48b314de1d3f9b79f0806` |

### Fact payload

#### `northwind::quote_usd`

```json
{
  "entity_key": "quote_usd",
  "evidence": {
    "excerpt": "Seed audit quote",
    "raw_artifact_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
    "source_type": "HUMAN_VERIFIED",
    "source_uri": "human://seed/audit"
  },
  "half_life_hours": 720.0,
  "initial_confidence": 0.9,
  "namespace": "northwind",
  "value": 48000
}
```

- **Evidence SHA-256:** `0000000000000000000000000000000000000000000000000000000000000000`
- **Evidence source:** `HUMAN_VERIFIED` — `human://seed/audit`
- **Evidence excerpt:** Seed audit quote

---

## Commit `ccd3557f87bf1d1fb92fd94cb00314a2b067cdf5fdc48b314de1d3f9b79f0806` [VALIDATED]

> **Status:** `VALIDATED`

| Field | Value |
| --- | --- |
| Agent | `seed-researcher` |
| Timestamp | `1700000000.000000 (2023-11-14T22:13:20Z)` |
| Branch | `main` |
| Parent commit | `—` |
| Causal parents | — |

### Fact payload

#### `northwind::tier`

```json
{
  "entity_key": "tier",
  "evidence": {
    "excerpt": "seed audit: northwind::tier=Professional",
    "raw_artifact_sha256": "dcd6a947e1188aae953045c5f94954022b4b5cf1e9f9915840054b296b2de168",
    "source_type": "TOOL_STDOUT",
    "source_uri": "tool://seed/audit"
  },
  "half_life_hours": 720.0,
  "initial_confidence": 0.94,
  "namespace": "northwind",
  "value": "Professional"
}
```

- **Evidence SHA-256:** `dcd6a947e1188aae953045c5f94954022b4b5cf1e9f9915840054b296b2de168`
- **Evidence source:** `TOOL_STDOUT` — `tool://seed/audit`
- **Evidence excerpt:** seed audit: northwind::tier=Professional
