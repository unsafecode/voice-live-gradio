"""Render minimal, focused diffs for the UI's "Switch diff" tab.

The whole point of this demo is *how few lines change* when you swap
Azure OpenAI Realtime → Azure Voice Live → Voice Live + Foundry Agent.
The full file diff buries that signal in docstring/import noise, so we
extract only the functions that actually carry the change
(``connect_factory`` always; ``make_session`` only if it differs) and
render a compact GitHub-style **unified** diff.
"""
from __future__ import annotations

import ast
import difflib
import html
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTEXT_LINES = 2

# Functions we surface, in order. If a function is missing from a file we
# just skip it — keeps the page robust when files are refactored.
FOCUS_FUNCTIONS = ("connect_factory", "make_session")


# ── helpers ───────────────────────────────────────────────────────────

def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _esc(s: str) -> str:
    return html.escape(s).replace("\t", "    ")


def _extract_function(source: str, name: str) -> list[str] | None:
    """Return the source lines of the top-level ``def NAME`` in ``source``.

    Uses ``ast`` to find the function span (handles multi-line signatures,
    decorators, async defs) and slices the original text so we keep the
    exact formatting the user wrote.
    """
    if not source:
        return None
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            start = (node.decorator_list[0].lineno if node.decorator_list else node.lineno) - 1
            end = (node.end_lineno or node.lineno)
            return source.splitlines()[start:end]
    return None


# ── diff rendering ────────────────────────────────────────────────────

@dataclass
class DiffStats:
    added: int
    removed: int
    hunks: int

    @property
    def changed_lines(self) -> int:
        return self.added + self.removed


def _compute_stats(left: list[str], right: list[str]) -> DiffStats:
    sm = difflib.SequenceMatcher(a=left, b=right, autojunk=False)
    added = removed = 0
    groups = list(sm.get_grouped_opcodes(n=CONTEXT_LINES))
    for group in groups:
        for tag, i1, i2, j1, j2 in group:
            if tag in ("replace", "delete"):
                removed += i2 - i1
            if tag in ("replace", "insert"):
                added += j2 - j1
    return DiffStats(added=added, removed=removed, hunks=len(groups))


def _render_unified(left: list[str], right: list[str]) -> str:
    """Render a compact, single-column unified diff (GitHub-style)."""
    sm = difflib.SequenceMatcher(a=left, b=right, autojunk=False)
    groups = list(sm.get_grouped_opcodes(n=CONTEXT_LINES))
    if not groups:
        return '<div class="vlx-diff-empty">No changes in this function.</div>'

    rows: list[str] = []

    def _row(kind: str, sign: str, ln_l: str, ln_r: str, code: str) -> str:
        return (
            f'<div class="vlx-row vlx-{kind}">'
            f'<span class="vlx-lno vlx-lno-l">{ln_l}</span>'
            f'<span class="vlx-lno vlx-lno-r">{ln_r}</span>'
            f'<span class="vlx-sign">{sign or "&nbsp;"}</span>'
            f'<span class="vlx-code">{_esc(code) if code else "&nbsp;"}</span>'
            f'</div>'
        )

    for gi, group in enumerate(groups):
        if gi > 0:
            rows.append('<div class="vlx-row vlx-gap"><span class="vlx-spacer"></span></div>')
        for tag, i1, i2, j1, j2 in group:
            if tag == "equal":
                for k in range(i2 - i1):
                    rows.append(_row("ctx", "", str(i1 + k + 1), str(j1 + k + 1), left[i1 + k]))
            elif tag == "replace":
                for k in range(i2 - i1):
                    rows.append(_row("del", "−", str(i1 + k + 1), "", left[i1 + k]))
                for k in range(j2 - j1):
                    rows.append(_row("add", "+", "", str(j1 + k + 1), right[j1 + k]))
            elif tag == "delete":
                for k in range(i2 - i1):
                    rows.append(_row("del", "−", str(i1 + k + 1), "", left[i1 + k]))
            elif tag == "insert":
                for k in range(j2 - j1):
                    rows.append(_row("add", "+", "", str(j1 + k + 1), right[j1 + k]))

    return f'<div class="vlx-diff">{"".join(rows)}</div>'


def _render_focus_panel(
    fn_name: str,
    left_source: str,
    right_source: str,
) -> str | None:
    """One ``<div class="vlx-panel">`` per changed function (or None if unchanged)."""
    left = _extract_function(left_source, fn_name)
    right = _extract_function(right_source, fn_name)
    if left is None or right is None or left == right:
        return None

    stats = _compute_stats(left, right)
    chips = (
        f'<span class="vlx-chip vlx-chip-add">+{stats.added}</span>'
        f'<span class="vlx-chip vlx-chip-del">−{stats.removed}</span>'
    )
    return (
        '<div class="vlx-panel">'
        f'<div class="vlx-panel-head">'
        f'<code class="vlx-fn">{html.escape(fn_name)}()</code>'
        f'<span class="vlx-stats">{chips}</span>'
        f'</div>'
        f'{_render_unified(left, right)}'
        '</div>'
    )


def _summary_chips(
    left_source: str,
    right_source: str,
    extra: list[str] | None = None,
) -> str:
    """Top-of-section chip row: total lines changed across all focus fns."""
    total_added = total_removed = 0
    fns_touched: list[str] = []
    for fn in FOCUS_FUNCTIONS:
        left = _extract_function(left_source, fn)
        right = _extract_function(right_source, fn)
        if left is None or right is None or left == right:
            continue
        s = _compute_stats(left, right)
        total_added += s.added
        total_removed += s.removed
        fns_touched.append(fn)

    chips = [
        f'<span class="vlx-summary-chip vlx-summary-chip-add">+{total_added} lines</span>',
        f'<span class="vlx-summary-chip vlx-summary-chip-del">−{total_removed} lines</span>',
        f'<span class="vlx-summary-chip">{len(fns_touched)} function{"s" if len(fns_touched) != 1 else ""} touched</span>',
    ]
    for e in (extra or []):
        chips.append(f'<span class="vlx-summary-chip vlx-summary-chip-info">{e}</span>')
    return f'<div class="vlx-summary">{"".join(chips)}</div>'


# ── top-level entry point ─────────────────────────────────────────────

def render_diffs_html() -> str:
    """Render the two key transitions as compact, minimal-noise diff cards."""
    rt = _read(REPO_ROOT / "app_realtime.py")
    vl = _read(REPO_ROOT / "app_voicelive.py")
    ag = _read(REPO_ROOT / "app_agent.py")

    def _section(
        step: str,
        title: str,
        lede: str,
        left_source: str,
        right_source: str,
        extra_chips: list[str],
    ) -> str:
        panels = [
            _render_focus_panel(fn, left_source, right_source)
            for fn in FOCUS_FUNCTIONS
        ]
        panels_html = "".join(p for p in panels if p)
        if not panels_html:
            panels_html = '<div class="vlx-diff-empty">No code changes in the focus functions.</div>'
        return (
            '<div class="vlx-section">'
            f'<div class="vlx-section-head">'
            f'<span class="vlx-step">{step}</span>'
            f'<span class="vlx-section-title">{title}</span>'
            f'</div>'
            f'<p class="vlx-lede">{lede}</p>'
            f'{_summary_chips(left_source, right_source, extra=extra_chips)}'
            f'{panels_html}'
            '</div>'
        )

    section1 = _section(
        step="1",
        title="Azure OpenAI Realtime → Azure Voice Live",
        lede=(
            "Same <code>AsyncAzureOpenAI</code> client, same "
            "<code>client.realtime.connect()</code> call. Three knobs change "
            "to point the SDK at the GA Voice Live endpoint."
        ),
        left_source=rt,
        right_source=vl,
        extra_chips=["Same SDK", "Same call shape"],
    )
    section2 = _section(
        step="2",
        title="Voice Live → Voice Live + Foundry Agent",
        lede=(
            "Same <code>connect_factory</code>. The <code>extra_query</code> "
            "dict is swapped: the model id is replaced by an agent id, "
            "project name, and short-lived agent access token."
        ),
        left_source=vl,
        right_source=ag,
        extra_chips=["Same SDK", "Agent owns instructions"],
    )

    return f'<div class="vlx-root">{section1}{section2}</div>'
