"""Typer + Rich CLI — viral terminal demo and ledger ops."""

from __future__ import annotations

import json
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from agentledger import __version__
from agentledger.engine import AgentLedgerEngine, ProvenanceFirewallError
from agentledger.models import EvidenceAnchor, MemoryCommit, MemoryFact, SourceType

app = typer.Typer(
    name="agentledger",
    help="Git-style version control for multi-agent shared memory.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()

DEFAULT_DB = Path(".agentledger") / "ledger.db"


# --------------------------------------------------------------------------- helpers


def _engine(db: Path | None = None) -> AgentLedgerEngine:
    path = DEFAULT_DB if db is None else db
    return AgentLedgerEngine(str(path))


def _status_badge(status: str) -> Text:
    if status == "VALIDATED":
        return Text("VALIDATED", style="bold bright_green")
    if status == "QUARANTINED":
        return Text("QUARANTINED", style="bold bright_red")
    return Text(status, style="yellow")


def _short(h: str, n: int = 12) -> str:
    return h[:n]


def _fact_keys(commit: MemoryCommit) -> str:
    return ", ".join(f"{f.namespace}::{f.entity_key}" for f in commit.facts) or "—"


def _format_timestamp(timestamp: float) -> str:
    """Render the stored Unix timestamp with a stable UTC representation."""
    utc = datetime.fromtimestamp(timestamp, tz=UTC).isoformat().replace("+00:00", "Z")
    return f"{timestamp:.6f} ({utc})"


def _markdown_audit(commits: list[MemoryCommit]) -> str:
    """Render complete commit and evidence provenance as Markdown."""
    lines = ["# AgentLedger Audit Export", ""]
    if not commits:
        lines.append("No commits found.")
        return "\n".join(lines) + "\n"

    lines.append(f"_Commits: {len(commits)} · Quarantined commits are marked explicitly._")
    lines.append("")
    for index, commit in enumerate(commits):
        marker = "[QUARANTINED]" if commit.status == "QUARANTINED" else "[VALIDATED]"
        lines.extend(
            [
                f"## Commit `{commit.commit_hash}` {marker}",
                "",
                f"> **Status:** `{commit.status}`",
            ]
        )
        if commit.status == "QUARANTINED":
            lines.append("> **QUARANTINED:** excluded from active memory until restored.")
        lines.extend(
            [
                "",
                "| Field | Value |",
                "| --- | --- |",
                f"| Agent | `{commit.agent_id}` |",
                f"| Timestamp | `{_format_timestamp(commit.timestamp)}` |",
                f"| Branch | `{commit.branch}` |",
                f"| Parent commit | `{commit.parent_hash or '—'}` |",
                f"| Causal parents | {_markdown_hash_list(commit.causal_read_hashes)} |",
                "",
                "### Fact payload",
                "",
            ]
        )
        if not commit.facts:
            lines.append("No facts.")
        for fact_index, fact in enumerate(commit.facts):
            evidence = fact.evidence
            lines.extend(
                [
                    f"#### `{fact.namespace}::{fact.entity_key}`",
                    "",
                    "```json",
                    json.dumps(fact.model_dump(mode="json"), indent=2, sort_keys=True),
                    "```",
                    "",
                    f"- **Evidence SHA-256:** `{evidence.raw_artifact_sha256}`",
                    f"- **Evidence source:** `{evidence.source_type.value}` — `{evidence.source_uri}`",
                ]
            )
            if evidence.excerpt:
                lines.append(f"- **Evidence excerpt:** {evidence.excerpt}")
            if fact_index != len(commit.facts) - 1:
                lines.append("")
        if index != len(commits) - 1:
            lines.extend(["", "---", ""])
    return "\n".join(lines) + "\n"


def _markdown_hash_list(hashes: list[str]) -> str:
    return ", ".join(f"`{value}`" for value in hashes) if hashes else "—"


def _decayed_for_commit(commit: MemoryCommit, now: float | None = None) -> str:
    ref = time.time() if now is None else now
    if not commit.facts:
        return "—"
    parts: list[str] = []
    for fact in commit.facts:
        conf = fact.current_confidence(commit.timestamp, now=ref)
        parts.append(f"{conf:.3f}")
    return ", ".join(parts)


def _make_tool_fact(
    engine: AgentLedgerEngine,
    *,
    namespace: str,
    entity_key: str,
    value: object,
    raw_text: str,
    confidence: float,
    source_uri: str,
) -> MemoryFact:
    digest = engine.register_artifact(raw_text)
    return MemoryFact(
        namespace=namespace,
        entity_key=entity_key,
        value=value,
        initial_confidence=confidence,
        evidence=EvidenceAnchor(
            source_type=SourceType.TOOL_STDOUT,
            source_uri=source_uri,
            raw_artifact_sha256=digest,
            excerpt=raw_text[:96],
        ),
    )


def _make_human_fact(
    *,
    namespace: str,
    entity_key: str,
    value: object,
    confidence: float,
    excerpt: str,
    source_uri: str,
) -> MemoryFact:
    return MemoryFact(
        namespace=namespace,
        entity_key=entity_key,
        value=value,
        initial_confidence=confidence,
        evidence=EvidenceAnchor(
            source_type=SourceType.HUMAN_VERIFIED,
            source_uri=source_uri,
            raw_artifact_sha256="0" * 64,
            excerpt=excerpt,
        ),
    )


def _print_commits_table(
    commits: list[MemoryCommit],
    *,
    title: str,
    now: float | None = None,
) -> None:
    table = Table(
        title=title,
        box=box.HEAVY_HEAD,
        header_style="bold bright_white",
        border_style="bright_cyan",
        show_lines=False,
    )
    table.add_column("Commit", style="cyan", no_wrap=True)
    table.add_column("Agent", style="bright_white")
    table.add_column("Status")
    table.add_column("Causal Parents", style="dim")
    table.add_column("Fact Keys", style="bright_yellow")
    table.add_column("Decayed Conf", justify="right")

    for c in commits:
        parents = (
            ", ".join(_short(h) for h in c.causal_read_hashes) if c.causal_read_hashes else "—"
        )
        table.add_row(
            _short(c.commit_hash),
            c.agent_id,
            _status_badge(c.status),
            parents,
            _fact_keys(c),
            _decayed_for_commit(c, now=now),
        )
    console.print(table)


# --------------------------------------------------------------------------- commands


@app.callback()
def main() -> None:
    """AgentLedger CLI."""


@app.command()
def version() -> None:
    """Print package version."""
    console.print(f"[bold]agentledger[/bold] {__version__}")


@app.command("demo")
def demo() -> None:
    """Viral 4-bot GTM demo: firewall catch + poisoned cascade rollback."""
    with tempfile.TemporaryDirectory(prefix="agentledger-demo-") as tmp:
        db_path = Path(tmp) / "demo.db"
        engine = AgentLedgerEngine(str(db_path))
        try:
            _run_demo(engine)
        finally:
            engine.close()


def _run_demo(engine: AgentLedgerEngine) -> None:
    t0 = time.time()

    # ---- Header ----
    header = Text()
    header.append("AGENTLEDGER", style="bold bright_cyan")
    header.append("  ·  ", style="dim")
    header.append("Provenance Firewall Demo", style="bold bright_white")
    header.append("\n\n")
    header.append("4-Bot GTM Group Project\n", style="bold underline bright_white")
    header.append("  bot-1-researcher", style="bold bright_magenta")
    header.append("   Scrapes prospect tech stack & budget\n", style="white")
    header.append("  bot-2-pricer", style="bold bright_yellow")
    header.append("       Reads researcher notes → calculates quote\n", style="white")
    header.append("  bot-3-copywriter", style="bold bright_green")
    header.append("   Reads quote → drafts outbound proposal\n", style="white")
    header.append("  bot-4-closer", style="bold bright_blue")
    header.append("      Approves & queues CRM dispatch\n", style="white")
    header.append("\n")
    header.append("Zero setup · temp SQLite · no API keys", style="dim italic")

    console.print(
        Panel(
            header,
            title="[bold]SCENE ZERO[/bold]",
            subtitle="multi-agent shared memory under adversarial input",
            border_style="bright_cyan",
            box=box.DOUBLE,
            padding=(1, 2),
        )
    )

    # =====================================================================
    # SCENE 1 — Pre-Commit Firewall Catch
    # =====================================================================
    console.print()
    console.print(Rule("[bold bright_red]SCENE 1[/bold bright_red]  The Pre-Commit Firewall Catch"))
    console.print()

    console.print(
        Panel(
            "[bold bright_magenta]bot-1-researcher[/bold bright_magenta] attempts to commit a "
            "[bold]hallucinated[/bold] fact with a [bold]fake receipt hash[/bold]:\n\n"
            "  [cyan]acme_corp::cloud_spend[/cyan] = [yellow]\"$2M/yr\"[/yellow]\n"
            "  receipt = [dim red]ffffffffffffffff…ffff[/dim red]  (never registered)",
            title="Hallucinated Write",
            border_style="bright_magenta",
            box=box.ROUNDED,
        )
    )

    fake = MemoryFact(
        namespace="acme_corp",
        entity_key="cloud_spend",
        value="$2M/yr",
        initial_confidence=0.97,
        evidence=EvidenceAnchor(
            source_type=SourceType.HTTP_RESPONSE,
            source_uri="https://scrape.local/acme/budget",
            raw_artifact_sha256="f" * 64,
            excerpt="hallucinated cloud spend estimate",
        ),
    )

    console.print(
        "[dim]→ agentledger.commit(agent_id='bot-1-researcher', strict_evidence=True)[/dim]"
    )
    try:
        engine.commit(agent_id="bot-1-researcher", facts=[fake], timestamp=t0)
        console.print("[bold red]FATAL: firewall failed to block hallucinated receipt[/bold red]")
        raise typer.Exit(code=1)
    except ProvenanceFirewallError as exc:
        console.print()
        console.print(
            Panel(
                f"[bold]{exc}[/bold]",
                title="[bold bright_red]FIREWALL BLOCKED[/bold bright_red]",
                border_style="bright_red",
                box=box.HEAVY,
                padding=(1, 2),
            )
        )
        console.print(
            "[bright_green]✓[/bright_green] Hallucination never entered shared memory."
        )

    # =====================================================================
    # SCENE 2 — Poisoned Cascade & Domino Rollback
    # =====================================================================
    console.print()
    console.print(
        Rule(
            "[bold bright_yellow]SCENE 2[/bold bright_yellow]  "
            "The Poisoned Cascade & Domino Rollback"
        )
    )
    console.print()

    # Poisoned but *registered* artifact (passes firewall, pollutes downstream)
    poison_raw = (
        'SCRAPE_OK acme_corp tier=Enterprise_Plus budget_signal=high '
        'source=broken_parser_v3 (POISONED)'
    )
    poison_fact = _make_tool_fact(
        engine,
        namespace="acme_corp",
        entity_key="tier",
        value="Enterprise_Plus",
        raw_text=poison_raw,
        confidence=0.93,
        source_uri="tool://scraper/acme",
    )
    c1 = engine.commit(
        agent_id="bot-1-researcher",
        facts=[poison_fact],
        causal_read_hashes=[],
        timestamp=t0 + 1,
    )
    console.print(
        f"[bright_magenta]bot-1-researcher[/bright_magenta] committed poisoned "
        f"[cyan]acme_corp::tier[/cyan]=[yellow]Enterprise_Plus[/yellow]  "
        f"[dim]{_short(c1.commit_hash)}[/dim]"
    )

    # bot-2-pricer reads researcher → quote
    _, reads1 = engine.read_facts(namespace="acme_corp", min_confidence=0.1, now=t0 + 2)
    quote_fact = _make_human_fact(
        namespace="acme_corp",
        entity_key="quote_usd",
        value=180_000,
        confidence=0.9,
        excerpt="Pricer: Enterprise_Plus → $180k ACV quote",
        source_uri="human://bot-2-pricer",
    )
    c2 = engine.commit(
        agent_id="bot-2-pricer",
        facts=[quote_fact],
        causal_read_hashes=[c1.commit_hash],
        timestamp=t0 + 10,
    )
    console.print(
        f"[bright_yellow]bot-2-pricer[/bright_yellow]     derived "
        f"[cyan]acme_corp::quote_usd[/cyan]=[yellow]180000[/yellow]  "
        f"← causal {_short(c1.commit_hash)}  [dim]{_short(c2.commit_hash)}[/dim]"
    )

    # bot-3-copywriter reads quote → proposal
    proposal_fact = _make_human_fact(
        namespace="acme_corp",
        entity_key="proposal_draft",
        value="Acme Enterprise_Plus rollout — $180k ACV, Q3 close",
        confidence=0.88,
        excerpt="Copywriter drafted outbound proposal from quote",
        source_uri="human://bot-3-copywriter",
    )
    c3 = engine.commit(
        agent_id="bot-3-copywriter",
        facts=[proposal_fact],
        causal_read_hashes=[c2.commit_hash],
        timestamp=t0 + 20,
    )
    console.print(
        f"[bright_green]bot-3-copywriter[/bright_green] drafted "
        f"[cyan]acme_corp::proposal_draft[/cyan]  "
        f"← causal {_short(c2.commit_hash)}  [dim]{_short(c3.commit_hash)}[/dim]"
    )

    # bot-4-closer reads proposal → CRM queue
    crm_fact = _make_human_fact(
        namespace="acme_corp",
        entity_key="crm_dispatch",
        value="QUEUED",
        confidence=0.86,
        excerpt="Closer approved proposal and queued CRM dispatch",
        source_uri="human://bot-4-closer",
    )
    c4 = engine.commit(
        agent_id="bot-4-closer",
        facts=[crm_fact],
        causal_read_hashes=[c3.commit_hash],
        timestamp=t0 + 30,
    )
    console.print(
        f"[bright_blue]bot-4-closer[/bright_blue]    queued "
        f"[cyan]acme_corp::crm_dispatch[/cyan]=[yellow]QUEUED[/yellow]  "
        f"← causal {_short(c3.commit_hash)}  [dim]{_short(c4.commit_hash)}[/dim]"
    )

    # Unrelated healthy commit (surgical precision control)
    healthy_raw = "SCRAPE_OK globex tier=Growth source=billing_export"
    healthy = _make_tool_fact(
        engine,
        namespace="globex",
        entity_key="tier",
        value="Growth",
        raw_text=healthy_raw,
        confidence=0.96,
        source_uri="tool://scraper/globex",
    )
    c_ok = engine.commit(
        agent_id="bot-1-researcher",
        facts=[healthy],
        causal_read_hashes=[],
        timestamp=t0 + 40,
    )
    console.print(
        f"[bright_white]unrelated[/bright_white]         healthy "
        f"[cyan]globex::tier[/cyan]=[yellow]Growth[/yellow]  "
        f"[dim]{_short(c_ok.commit_hash)}[/dim]  "
        f"[bright_green](no causal link to poison)[/bright_green]"
    )

    # Silence unused reads1 warning by referencing it
    _ = reads1

    # ---- Memory DAG tree ----
    console.print()
    dag = Tree(
        "[bold bright_cyan]Active Memory DAG[/bold bright_cyan]  "
        "[dim](causal_read_hashes)[/dim]"
    )
    n1 = dag.add(
        f"[bright_red]●[/bright_red] [bold]{_short(c1.commit_hash)}[/bold]  "
        f"[bright_magenta]bot-1-researcher[/bright_magenta]  "
        f"[cyan]acme_corp::tier[/cyan]=Enterprise_Plus  [dim]POISON ROOT[/dim]"
    )
    n2 = n1.add(
        f"[bright_yellow]●[/bright_yellow] [bold]{_short(c2.commit_hash)}[/bold]  "
        f"[bright_yellow]bot-2-pricer[/bright_yellow]  "
        f"[cyan]acme_corp::quote_usd[/cyan]=180000"
    )
    n3 = n2.add(
        f"[bright_green]●[/bright_green] [bold]{_short(c3.commit_hash)}[/bold]  "
        f"[bright_green]bot-3-copywriter[/bright_green]  "
        f"[cyan]acme_corp::proposal_draft[/cyan]"
    )
    n3.add(
        f"[bright_blue]●[/bright_blue] [bold]{_short(c4.commit_hash)}[/bold]  "
        f"[bright_blue]bot-4-closer[/bright_blue]  "
        f"[cyan]acme_corp::crm_dispatch[/cyan]=QUEUED"
    )
    dag.add(
        f"[bright_green]●[/bright_green] [bold]{_short(c_ok.commit_hash)}[/bold]  "
        f"[bright_white]bot-1-researcher[/bright_white]  "
        f"[cyan]globex::tier[/cyan]=Growth  [bright_green]UNRELATED[/bright_green]"
    )
    console.print(
        Panel(dag, title="Causal Dependency Graph", border_style="bright_cyan", box=box.ROUNDED)
    )

    # ---- Domino rollback ----
    console.print()
    console.print(
        f"[bold]→ revert_cascade({_short(c1.commit_hash)!r})[/bold]  "
        "[dim]BFS across causal_read_hashes[/dim]"
    )
    quarantined = engine.revert_cascade(c1.commit_hash)

    qtree = Tree(
        f"[bold bright_red]Domino Quarantine[/bold bright_red]  "
        f"({len(quarantined)} commits)"
    )
    labels = {
        c1.commit_hash: "bot-1-researcher  acme_corp::tier  [POISON ROOT]",
        c2.commit_hash: "bot-2-pricer      acme_corp::quote_usd",
        c3.commit_hash: "bot-3-copywriter  acme_corp::proposal_draft",
        c4.commit_hash: "bot-4-closer     acme_corp::crm_dispatch",
    }
    cursor = qtree
    for i, ch in enumerate(quarantined):
        label = labels.get(ch, ch)
        node_text = f"[bright_red]{_short(ch)}[/bright_red]  {label}"
        if i == 0:
            cursor = qtree.add(node_text)
        else:
            cursor = cursor.add(node_text)
    console.print(qtree)

    # ---- Final state table ----
    console.print()
    all_commits = engine.list_commits(include_quarantined=True)
    # Stable demo order: by timestamp ascending for narrative clarity
    all_commits_sorted = sorted(all_commits, key=lambda c: c.timestamp)
    _print_commits_table(
        all_commits_sorted,
        title="Final Ledger State — Surgical Precision",
        now=t0 + 50,
    )

    poisoned_set = {c1.commit_hash, c2.commit_hash, c3.commit_hash, c4.commit_hash}
    for ch in poisoned_set:
        st = engine.get_commit(ch)
        assert st is not None and st.status == "QUARANTINED"
    ok = engine.get_commit(c_ok.commit_hash)
    assert ok is not None and ok.status == "VALIDATED"

    console.print()
    console.print(
        Panel(
            "[bold bright_green]PASS[/bold bright_green]  "
            "4 poisoned commits → [bold red]QUARANTINED[/bold red]\n"
            "[bold bright_green]PASS[/bold bright_green]  "
            "[cyan]globex::tier[/cyan] remains [bold green]VALIDATED[/bold green]\n"
            "[dim]Provenance Firewall blocked the hallucination; "
            "BFS cascade surgically rolled back the poison chain.[/dim]",
            title="Demo Result",
            border_style="bright_green",
            box=box.DOUBLE,
        )
    )


@app.command("log")
def log_cmd(
    db: Path | None = typer.Option(
        None, "--db", help="SQLite path (default .agentledger/ledger.db)"
    ),
    all_statuses: bool = typer.Option(
        True,
        "--all/--validated-only",
        help="Include QUARANTINED commits (default: all).",
    ),
) -> None:
    """Show commit history with status, causal parents, facts, and decayed confidence."""
    engine = _engine(db)
    try:
        commits = engine.list_commits(include_quarantined=all_statuses)
        if not commits:
            console.print(
                Panel(
                    "[dim]Ledger is empty. Run[/dim] [bold]agentledger seed[/bold] "
                    "[dim]or[/dim] [bold]agentledger demo[/bold][dim].[/dim]",
                    border_style="yellow",
                )
            )
            return
        _print_commits_table(commits, title=f"agentledger log  ·  {engine.db_path}")
    finally:
        engine.close()


@app.command("export")
def export_cmd(
    db: Path | None = typer.Option(
        None, "--db", help="SQLite path (default .agentledger/ledger.db)"
    ),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write Markdown to this file instead of stdout"
    ),
    all_statuses: bool = typer.Option(
        True,
        "--all/--validated-only",
        help="Include QUARANTINED commits (default: all).",
    ),
) -> None:
    """Export commit history, facts, and evidence receipts as Markdown."""
    engine = _engine(db)
    try:
        markdown = _markdown_audit(
            engine.list_commits(include_quarantined=all_statuses)
        )
    finally:
        engine.close()

    if output is None:
        typer.echo(markdown, nl=False)
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")
    console.print(f"[bright_green]Exported audit Markdown[/bright_green] to {output}")


@app.command("blame")
def blame_cmd(
    entity_key: str = typer.Argument(..., help="Entity key to inspect (e.g. tier)"),
    db: Path | None = typer.Option(None, "--db", help="SQLite path"),
) -> None:
    """Show full provenance receipt for an active entity key."""
    engine = _engine(db)
    try:
        hit = engine.blame(entity_key)
        if hit is None:
            console.print(
                Panel(
                    f"No [bold]VALIDATED[/bold] active fact for "
                    f"[cyan]{entity_key!r}[/cyan]",
                    title="blame",
                    border_style="yellow",
                )
            )
            raise typer.Exit(code=1)

        ev = hit["evidence"]
        body = Text()
        body.append(f"{hit['namespace']}::{hit['entity_key']}", style="bold bright_cyan")
        body.append("  =  ", style="dim")
        body.append(repr(hit["value"]), style="bold bright_yellow")
        body.append("\n\n")
        body.append("agent_id          ", style="dim")
        body.append(f"{hit['agent_id']}\n", style="bright_white")
        body.append("commit_hash       ", style="dim")
        body.append(f"{hit['commit_hash']}\n", style="cyan")
        body.append("timestamp         ", style="dim")
        body.append(f"{hit['timestamp']}\n")
        body.append("current_confidence", style="dim")
        body.append(f"  {hit['current_confidence']:.6f}\n", style="bright_green")
        body.append("initial_confidence", style="dim")
        body.append(f"  {hit['initial_confidence']:.6f}\n")
        body.append("\n")
        body.append("── evidence receipt ──\n", style="bold bright_white")
        body.append("source_type       ", style="dim")
        body.append(f"{ev['source_type']}\n", style="bright_magenta")
        body.append("source_uri        ", style="dim")
        body.append(f"{ev['source_uri']}\n")
        body.append("raw_artifact_sha256\n  ", style="dim")
        body.append(f"{ev['raw_artifact_sha256']}\n", style="cyan")
        body.append("excerpt           ", style="dim")
        body.append(f"{ev.get('excerpt', '')}\n", style="italic")

        console.print(
            Panel(
                body,
                title=f"[bold]blame[/bold] {entity_key}",
                border_style="bright_white",
                box=box.HEAVY_HEAD,
                padding=(1, 2),
            )
        )
    finally:
        engine.close()


@app.command("revert")
def revert_cmd(
    commit_hash_prefix: str = typer.Argument(
        ..., help="Full commit hash or unique prefix"
    ),
    db: Path | None = typer.Option(None, "--db", help="SQLite path"),
) -> None:
    """BFS-quarantine a commit (by hash prefix) and all causal dependents."""
    engine = _engine(db)
    try:
        try:
            target = engine.resolve_commit_prefix(commit_hash_prefix)
        except KeyError as exc:
            console.print(Panel(str(exc), title="revert", border_style="red"))
            raise typer.Exit(code=1) from exc
        except ValueError as exc:
            console.print(Panel(str(exc), title="revert", border_style="yellow"))
            raise typer.Exit(code=1) from exc

        console.print(
            f"[dim]resolved[/dim] {_short(target.commit_hash)}  "
            f"[bright_white]{target.agent_id}[/bright_white]  "
            f"{_fact_keys(target)}"
        )
        quarantined = engine.revert_cascade(target.commit_hash)

        tree = Tree(
            f"[bold bright_red]quarantined[/bold bright_red]  "
            f"({len(quarantined)} commits)"
        )
        node = tree
        for i, ch in enumerate(quarantined):
            c = engine.get_commit(ch)
            label = (
                f"[red]{_short(ch)}[/red]  {c.agent_id}  {_fact_keys(c)}"
                if c
                else f"[red]{_short(ch)}[/red]"
            )
            if i == 0:
                node = tree.add(label + "  [dim]ROOT[/dim]")
            else:
                node = node.add(label)
        console.print(tree)
    finally:
        engine.close()


@app.command("seed")
def seed(
    db: Path | None = typer.Option(None, "--db", help="SQLite path"),
    force: bool = typer.Option(
        False, "--force", help="Seed even if the ledger already has commits"
    ),
) -> None:
    """Populate the local ledger with sample multi-agent commits for manual testing."""
    engine = _engine(db)
    try:
        existing = engine.list_commits(include_quarantined=True)
        if existing and not force:
            console.print(
                Panel(
                    f"Ledger already has [bold]{len(existing)}[/bold] commits at "
                    f"[cyan]{engine.db_path}[/cyan].\n"
                    "Use [bold]--force[/bold] to append another sample chain, or "
                    "[bold]agentledger log[/bold] to inspect.",
                    title="seed",
                    border_style="yellow",
                )
            )
            return

        t = time.time()
        raw = "SEED scrape: northwind::tier=Professional seats=42"
        f1 = _make_tool_fact(
            engine,
            namespace="northwind",
            entity_key="tier",
            value="Professional",
            raw_text=raw,
            confidence=0.94,
            source_uri="tool://seed/scraper",
        )
        c1 = engine.commit(
            agent_id="bot-1-researcher",
            facts=[f1],
            causal_read_hashes=[],
            timestamp=t,
        )

        f2 = _make_human_fact(
            namespace="northwind",
            entity_key="quote_usd",
            value=48_000,
            confidence=0.9,
            excerpt="Seed pricer quote from Professional tier",
            source_uri="human://seed/pricer",
        )
        c2 = engine.commit(
            agent_id="bot-2-pricer",
            facts=[f2],
            causal_read_hashes=[c1.commit_hash],
            timestamp=t + 5,
        )

        f3 = _make_human_fact(
            namespace="northwind",
            entity_key="proposal_draft",
            value="Northwind Professional — $48k pilot",
            confidence=0.87,
            excerpt="Seed copywriter proposal",
            source_uri="human://seed/copywriter",
        )
        c3 = engine.commit(
            agent_id="bot-3-copywriter",
            facts=[f3],
            causal_read_hashes=[c2.commit_hash],
            timestamp=t + 10,
        )

        f4 = _make_human_fact(
            namespace="northwind",
            entity_key="crm_dispatch",
            value="QUEUED",
            confidence=0.85,
            excerpt="Seed closer CRM queue",
            source_uri="human://seed/closer",
        )
        c4 = engine.commit(
            agent_id="bot-4-closer",
            facts=[f4],
            causal_read_hashes=[c3.commit_hash],
            timestamp=t + 15,
        )

        side_raw = "SEED scrape: contoso::tier=Starter"
        side = _make_tool_fact(
            engine,
            namespace="contoso",
            entity_key="tier",
            value="Starter",
            raw_text=side_raw,
            confidence=0.91,
            source_uri="tool://seed/scraper",
        )
        c_side = engine.commit(
            agent_id="bot-1-researcher",
            facts=[side],
            causal_read_hashes=[],
            timestamp=t + 20,
        )

        tree = Tree(f"[bold bright_green]seeded[/bold bright_green]  {engine.db_path}")
        n = tree.add(f"{_short(c1.commit_hash)}  bot-1-researcher  northwind::tier")
        n = n.add(f"{_short(c2.commit_hash)}  bot-2-pricer  northwind::quote_usd")
        n = n.add(f"{_short(c3.commit_hash)}  bot-3-copywriter  northwind::proposal_draft")
        n.add(f"{_short(c4.commit_hash)}  bot-4-closer  northwind::crm_dispatch")
        tree.add(
            f"{_short(c_side.commit_hash)}  bot-1-researcher  "
            "contoso::tier  [dim]unrelated[/dim]"
        )
        console.print(Panel(tree, title="agentledger seed", border_style="bright_green"))
        console.print(
            "[dim]Try:[/dim]  [bold]agentledger log[/bold]  ·  "
            "[bold]agentledger blame tier[/bold]  ·  "
            f"[bold]agentledger revert {_short(c1.commit_hash)}[/bold]"
        )
    finally:
        engine.close()


@app.command("mcp")
def mcp_cmd() -> None:
    """Start the AgentLedger FastMCP stdio server (Cursor / Claude / LangGraph)."""
    from agentledger.mcp_server import main as mcp_main

    console.print(
        Panel(
            "[bold]AgentLedger MCP[/bold] listening on stdio\n"
            "[dim]Tools: ledger_register_evidence · ledger_read · ledger_commit · "
            "ledger_blame · ledger_revert_cascade[/dim]",
            border_style="bright_cyan",
            box=box.ROUNDED,
        )
    )
    mcp_main()


if __name__ == "__main__":
    app()
