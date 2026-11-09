"""Shared writer for docs/claims_to_evidence.md, the macro -> value -> source ledger of the paper.

evaluation/make_tables.py writes the head of the file (its own macros). Other generators (make_hardware.py,
make_learned.py) own one "## <title>" section each and replace only that section, so running the generators in any
order leaves every section in place.
"""
from pathlib import Path
from typing import Iterable, Tuple

LEDGER = Path(__file__).resolve().parent.parent / "docs" / "claims_to_evidence.md"


def cell(text: str) -> str:
    return str(text).replace("|", "/").replace("\n", " ")


def table(rows: Iterable[Tuple[str, str, str, str]]) -> str:
    """Markdown table of (macro, value, source, how computed)."""
    lines = ["| Macro | Value | Source | How computed |", "| --- | --- | --- | --- |"]
    lines += [f"| `\\{n}` | {cell(v)} | `{cell(s)}` | {cell(h)} |" for n, v, s, h in rows]
    return "\n".join(lines) + "\n"


def sections_after_head(text: str) -> str:
    """Everything from the first '## ' heading on (the sections other generators own)."""
    i = text.find("\n## ")
    return "" if i < 0 else text[i + 1:]


def write_head(head: str, path: Path = LEDGER) -> None:
    """Replace the head of the ledger (before the first '## ' section), keeping every section."""
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    tail = sections_after_head(old)
    path.write_text(head.rstrip("\n") + "\n" + ("\n" + tail if tail else ""), encoding="utf-8")


def write_section(title: str, intro: str, rows: Iterable[Tuple[str, str, str, str]], path: Path = LEDGER) -> None:
    """Replace (or append) the section '## <title>' of the ledger."""
    text = path.read_text(encoding="utf-8") if path.exists() else "# Claims-to-evidence ledger\n"
    body = f"## {title}\n\n{intro.strip()}\n\n{table(rows)}"
    start = text.find(f"\n## {title}\n")
    if start < 0:
        text = text.rstrip("\n") + "\n\n" + body
    else:
        nxt = text.find("\n## ", start + 1)
        text = text[:start + 1] + body + ("" if nxt < 0 else "\n" + text[nxt + 1:])
    path.write_text(text, encoding="utf-8")
