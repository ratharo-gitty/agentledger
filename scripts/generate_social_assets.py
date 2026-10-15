#!/usr/bin/env python3
"""Render social launch stills (firewall block + code card) as dark-mode SVGs."""

from __future__ import annotations

from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"


def render_firewall_blocked() -> Path:
    """Asset 2: high-contrast Provenance Firewall intercept still."""
    out = ASSETS / "firewall_blocked.svg"
    console = Console(record=True, width=80, force_terminal=True, color_system="truecolor")

    body = Text()
    body.append("Agent:         ", style="dim")
    body.append("bot-1-researcher\n", style="bold bright_magenta")
    body.append("Target Key:    ", style="dim")
    body.append("acme_corp::cloud_spend\n", style="bold cyan")
    body.append("Value:         ", style="dim")
    body.append('"$2,000,000 / yr"\n', style="bold bright_yellow")
    body.append("Receipt Hash:  ", style="dim")
    body.append(
        "0000000000000000000000000000000000000000000000000000000000000000\n",
        style="dim red",
    )
    body.append("\n")
    body.append("Status:        ", style="dim")
    body.append("BLOCKED: UNVERIFIED_RECEIPT\n", style="bold red")
    body.append("\n")
    body.append(
        "ProvenanceFirewallError: Hash not present in SQLite artifacts table.",
        style="bold red",
    )

    console.print(
        Panel(
            body,
            title="[bold red]PROVENANCE FIREWALL INTERCEPT[/]",
            border_style="bold red",
            box=box.HEAVY,
            padding=(1, 2),
        )
    )
    console.save_svg(str(out), title="AgentLedger Firewall Block")
    return out


def render_code_snippet() -> Path:
    """Asset 3: syntax-highlighted 9-line ergonomic API card."""
    out = ASSETS / "code_snippet.svg"
    console = Console(record=True, width=85, force_terminal=True, color_system="truecolor")

    code = """from agentledger import ledger

# 1. Automatically hash & anchor tool output
@ledger.watch(key="acme::budget")
def fetch_budget():
    return "Approved budget: $500,000"

# 2. Causal dependency tracking across agent hops
with ledger.agent("pricer-bot"):
    budget = ledger.get("acme::budget")  # Automatically tracks read
    ledger.set("acme::quote", 75000)     # Automatically links causal lineage
"""
    syntax = Syntax(
        code,
        "python",
        theme="monokai",
        line_numbers=True,
        word_wrap=False,
        background_color="default",
    )
    console.print(
        Panel(
            syntax,
            title="[bold cyan]agentledger • Python Integration[/]",
            border_style="bright_cyan",
            box=box.ROUNDED,
            padding=(1, 1),
        )
    )
    console.save_svg(str(out), title="AgentLedger Code Snippet")
    return out


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    firewall = render_firewall_blocked()
    snippet = render_code_snippet()
    for path in (firewall, snippet):
        size = path.stat().st_size
        text = path.read_text(encoding="utf-8")
        if size <= 0 or "<svg" not in text:
            raise SystemExit(f"error: invalid asset {path}")
        print(f"wrote {path.relative_to(ROOT)} ({size} bytes)")


if __name__ == "__main__":
    main()
