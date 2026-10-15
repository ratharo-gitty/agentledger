#!/usr/bin/env python3
"""Publish the 6 issues from GOOD_FIRST_ISSUES.md via `gh issue create`."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "GOOD_FIRST_ISSUES.md"
LABELS = ["good first issue", "help wanted"]


def parse_issues(text: str) -> list[tuple[str, str]]:
    """Return (title, body) pairs from the GOOD_FIRST_ISSUES.md template file."""
    chunks = re.split(r"\n---\n", text)
    issues: list[tuple[str, str]] = []
    for chunk in chunks:
        title_m = re.search(r"\*\*Title:\*\*\s+`([^`]+)`", chunk)
        body_m = re.search(r"```markdown\n(.*?)```", chunk, re.DOTALL)
        if not title_m or not body_m:
            continue
        issues.append((title_m.group(1).strip(), body_m.group(1).strip() + "\n"))
    return issues


def main() -> int:
    issues = parse_issues(DOC.read_text(encoding="utf-8"))
    if len(issues) != 6:
        print(f"error: expected 6 issues, parsed {len(issues)}", file=sys.stderr)
        return 1

    # Ensure labels exist (ignore errors if they already do).
    for label in LABELS:
        color = "7057ff" if label == "good first issue" else "008672"
        subprocess.run(
            ["gh", "label", "create", label, "--color", color, "--force"],
            cwd=ROOT,
            check=False,
            capture_output=True,
        )

    created: list[str] = []
    for title, body in issues:
        result = subprocess.run(
            [
                "gh",
                "issue",
                "create",
                "--title",
                title,
                "--body",
                body,
                "--label",
                LABELS[0],
                "--label",
                LABELS[1],
            ],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        url = result.stdout.strip()
        created.append(url)
        print(url)

    print(f"\npublished {len(created)} issues", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
