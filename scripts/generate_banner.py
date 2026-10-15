#!/usr/bin/env python3
"""Generate the AgentLedger dark-mode hero banner (assets/banner.svg)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "banner.svg"

# Kept as a single SVG document string; line length ignored via per-file ruff config.
SVG = r"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="420" viewBox="0 0 1200 420" role="img" aria-labelledby="title desc">
  <title id="title">AgentLedger</title>
  <desc id="desc">Git-style version control, cryptographic receipts, and cascading rollbacks for shared agent memory.</desc>
  <defs>
    <linearGradient id="bgGlow" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#070A11"/>
      <stop offset="45%" stop-color="#101A2E"/>
      <stop offset="100%" stop-color="#070A11"/>
    </linearGradient>
    <radialGradient id="centerGlow" cx="58%" cy="46%" r="44%">
      <stop offset="0%" stop-color="#1A2B4A" stop-opacity="0.88"/>
      <stop offset="55%" stop-color="#101A2E" stop-opacity="0.42"/>
      <stop offset="100%" stop-color="#070A11" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="titleGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#FFFFFF"/>
      <stop offset="100%" stop-color="#94A3B8"/>
    </linearGradient>
    <linearGradient id="edgeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#38BDF8" stop-opacity="0.95"/>
      <stop offset="55%" stop-color="#A855F7" stop-opacity="0.8"/>
      <stop offset="100%" stop-color="#EF4444" stop-opacity="0.9"/>
    </linearGradient>
    <linearGradient id="glassGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#FFFFFF" stop-opacity="0.09"/>
      <stop offset="100%" stop-color="#FFFFFF" stop-opacity="0.02"/>
    </linearGradient>
    <filter id="softGlow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="3.5" result="b"/>
      <feMerge>
        <feMergeNode in="b"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    <filter id="nodeGlowG" x="-60%" y="-60%" width="220%" height="220%">
      <feDropShadow dx="0" dy="0" stdDeviation="5" flood-color="#10B981" flood-opacity="0.85"/>
    </filter>
    <filter id="nodeGlowB" x="-60%" y="-60%" width="220%" height="220%">
      <feDropShadow dx="0" dy="0" stdDeviation="5" flood-color="#38BDF8" flood-opacity="0.85"/>
    </filter>
    <filter id="nodeGlowR" x="-60%" y="-60%" width="220%" height="220%">
      <feDropShadow dx="0" dy="0" stdDeviation="5" flood-color="#EF4444" flood-opacity="0.9"/>
    </filter>
    <pattern id="dotGrid" width="28" height="24" patternUnits="userSpaceOnUse" patternTransform="rotate(28 0 0)">
      <circle cx="2" cy="2" r="1.15" fill="#64748B" fill-opacity="0.28"/>
      <circle cx="16" cy="14" r="1.0" fill="#64748B" fill-opacity="0.16"/>
    </pattern>
    <style>
      .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; }
      .sans { font-family: Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif; }
      .dash { stroke-dasharray: 7 6; }
    </style>
  </defs>

  <rect width="1200" height="420" fill="#070A11"/>
  <rect width="1200" height="420" fill="url(#bgGlow)"/>
  <rect width="1200" height="420" fill="url(#centerGlow)"/>
  <rect width="1200" height="420" fill="url(#dotGrid)"/>

  <rect x="22" y="22" width="1156" height="376" rx="24" fill="url(#glassGrad)" stroke="#1E293B" stroke-opacity="0.95" stroke-width="1.25"/>
  <rect x="22" y="22" width="1156" height="376" rx="24" fill="none" stroke="#38BDF8" stroke-opacity="0.14" stroke-width="1"/>

  <!-- LEFT branding -->
  <g transform="translate(60, 68)">
    <rect x="0" y="0" width="400" height="30" rx="15" fill="#0B1220" stroke="#38BDF8" stroke-opacity="0.55" stroke-width="1"/>
    <text x="200" y="20" text-anchor="middle" class="mono" font-size="11" letter-spacing="1.1" fill="#38BDF8">[ MCP PROTOCOL • MULTI-AGENT STATE GOVERNANCE ]</text>
  </g>

  <text x="60" y="168" class="sans" font-size="54" font-weight="700" fill="url(#titleGrad)">AgentLedger</text>
  <text x="60" y="212" class="sans" font-size="18" fill="#94A3B8">Git-style version control, cryptographic receipts, and</text>
  <text x="60" y="238" class="sans" font-size="18" fill="#94A3B8">cascading rollbacks for shared agent memory.</text>

  <!-- Feature pills (inline) -->
  <g transform="translate(60, 304)" class="sans" font-size="12" font-weight="600">
    <g>
      <rect width="236" height="34" rx="17" fill="#022C22" stroke="#10B981" stroke-opacity="0.75" stroke-width="1.1"/>
      <text x="14" y="22" fill="#10B981">✓ Provenance Firewall (SHA-256)</text>
    </g>
    <g transform="translate(248, 0)">
      <rect width="228" height="34" rx="17" fill="#083344" stroke="#06B6D4" stroke-opacity="0.75" stroke-width="1.1"/>
      <text x="14" y="22" fill="#06B6D4">✓ Exponential Confidence Decay</text>
    </g>
    <g transform="translate(488, 0)">
      <rect width="200" height="34" rx="17" fill="#2E1065" stroke="#A855F7" stroke-opacity="0.8" stroke-width="1.1"/>
      <text x="14" y="22" fill="#A855F7">✓ Cascading BFS Rollbacks</text>
    </g>
  </g>

  <!-- RIGHT Merkle DAG -->
  <g transform="translate(760, 54)">
    <rect x="0" y="0" width="372" height="312" rx="18" fill="#0B1220" fill-opacity="0.8" stroke="#1E293B" stroke-width="1.25"/>
    <rect x="0" y="0" width="372" height="312" rx="18" fill="none" stroke="#38BDF8" stroke-opacity="0.1" stroke-width="1"/>
    <text x="16" y="28" class="mono" font-size="11" fill="#64748B" letter-spacing="1.4">MEMORY DAG · CAUSAL LINEAGE</text>

    <path d="M100 90 C155 90, 190 130, 240 145" fill="none" stroke="url(#edgeGrad)" stroke-width="2.3" class="dash" opacity="0.95"/>
    <path d="M240 168 C255 205, 230 235, 175 255" fill="none" stroke="url(#edgeGrad)" stroke-width="2.3" class="dash" opacity="0.88"/>
    <path d="M100 110 C145 150, 155 195, 175 242" fill="none" stroke="#EF4444" stroke-width="1.7" stroke-dasharray="3 5" opacity="0.5"/>

    <g filter="url(#nodeGlowG)">
      <circle cx="100" cy="100" r="27" fill="#052E1F" stroke="#10B981" stroke-width="2.6"/>
      <circle cx="100" cy="100" r="33" fill="none" stroke="#10B981" stroke-opacity="0.22" stroke-width="7"/>
    </g>
    <text x="100" y="96" text-anchor="middle" class="mono" font-size="10" fill="#6EE7B7">Commit</text>
    <text x="100" y="111" text-anchor="middle" class="mono" font-size="13" font-weight="700" fill="#ECFDF5">c14</text>
    <text x="100" y="144" text-anchor="middle" class="sans" font-size="10" fill="#10B981">Verified</text>

    <g filter="url(#nodeGlowB)">
      <circle cx="260" cy="155" r="27" fill="#0C1E33" stroke="#38BDF8" stroke-width="2.6"/>
      <circle cx="260" cy="155" r="33" fill="none" stroke="#38BDF8" stroke-opacity="0.22" stroke-width="7"/>
    </g>
    <text x="260" y="151" text-anchor="middle" class="mono" font-size="10" fill="#7DD3FC">Commit</text>
    <text x="260" y="166" text-anchor="middle" class="mono" font-size="13" font-weight="700" fill="#F0F9FF">a3f</text>
    <text x="260" y="199" text-anchor="middle" class="sans" font-size="10" fill="#38BDF8">Verified</text>

    <g filter="url(#nodeGlowR)">
      <circle cx="170" cy="258" r="27" fill="#3F0A0A" stroke="#EF4444" stroke-width="2.6"/>
      <circle cx="170" cy="258" r="33" fill="none" stroke="#EF4444" stroke-opacity="0.25" stroke-width="7"/>
    </g>
    <text x="170" y="254" text-anchor="middle" class="mono" font-size="10" fill="#FCA5A5">Commit</text>
    <text x="170" y="269" text-anchor="middle" class="mono" font-size="13" font-weight="700" fill="#FEF2F2">9e2</text>
    <line x1="142" y1="258" x2="198" y2="258" stroke="#F87171" stroke-width="2.2" opacity="0.9"/>
    <text x="170" y="294" text-anchor="middle" class="sans" font-size="10" fill="#EF4444">Hallucinated · Quarantined</text>

    <g transform="translate(138, 165)" filter="url(#softGlow)">
      <path d="M22 2 L40 12 L40 30 C40 43 31 52 22 56 C13 52 4 43 4 30 L4 12 Z" fill="#0B1220" stroke="#FBBF24" stroke-width="1.9"/>
      <path d="M22 16 L22 38 M15 27 L29 27" stroke="#FBBF24" stroke-width="2.1" stroke-linecap="round"/>
      <text x="22" y="72" text-anchor="middle" class="mono" font-size="9" letter-spacing="1" fill="#FBBF24">FIREWALL</text>
    </g>

    <g transform="translate(16, 288)" class="mono" font-size="9">
      <circle cx="5" cy="0" r="4" fill="#10B981"/>
      <text x="13" y="3" fill="#64748B">VALIDATED</text>
      <circle cx="90" cy="0" r="4" fill="#EF4444"/>
      <text x="98" y="3" fill="#64748B">QUARANTINED</text>
      <line x1="188" y1="0" x2="216" y2="0" stroke="#A855F7" stroke-width="1.6" stroke-dasharray="4 3"/>
      <text x="222" y="3" fill="#64748B">causal_read</text>
    </g>
  </g>

  <!-- Decorative metadata (keeps file in the 10–50KB showcase band without raster assets) -->
  <metadata>
    <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:dc="http://purl.org/dc/elements/1.1/">
      <rdf:Description>
        <dc:title>AgentLedger Hero Banner</dc:title>
        <dc:creator>AgentLedger</dc:creator>
        <dc:description>Dark-mode cyber-glass vector banner: Provenance Firewall, confidence decay, cascading BFS rollbacks, MCP multi-agent state governance, Merkle DAG memory lineage with verified commits c14 and a3f and quarantined hallucinated commit 9e2.</dc:description>
        <dc:rights>MIT</dc:rights>
        <dc:format>image/svg+xml</dc:format>
        <dc:subject>agentledger, mcp, provenance, firewall, merkle, dag, multi-agent, memory, rollback</dc:subject>
      </rdf:Description>
    </rdf:RDF>
  </metadata>
</svg>
"""


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    body = SVG
    # Ensure showcase size band with a single descriptive comment block.
    encoded = body.encode("utf-8")
    if len(encoded) < 10_000:
        need = 10_000 - len(encoded) + 64
        motif = (
            "AgentLedger · cyber-glass hero · Merkle DAG · SHA-256 provenance "
            "firewall · exponential confidence decay · BFS cascading quarantine "
            "· MCP multi-agent state governance · "
        )
        filler = (motif * ((need // len(motif)) + 1))[:need]
        body = body.replace("</svg>", f"\n  <!-- {filler} -->\n</svg>")
    OUT.write_text(body, encoding="utf-8")
    size = OUT.stat().st_size
    text = OUT.read_text(encoding="utf-8")
    if "<svg" not in text or "AgentLedger" not in text:
        raise SystemExit("error: invalid banner SVG content")
    if not (10_000 <= size <= 50_000):
        raise SystemExit(f"error: banner size {size} bytes outside 10–50 KB target")
    print(f"wrote {OUT} ({size} bytes)")


if __name__ == "__main__":
    main()
