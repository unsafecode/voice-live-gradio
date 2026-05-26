"""Render side-by-side diffs between the three rung apps for the UI's diff tab.

We roll our own diff renderer — `difflib.HtmlDiff` produces a 1998-era table
that's not worth styling around. This one emits a CSS-Grid layout that looks
like GitHub's split view: line numbers, ± gutter, color-coded rows, only the
changed hunks plus 3 lines of context.
"""
from __future__ import annotations

import difflib
import html
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTEXT_LINES = 3


def _read(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines(keepends=False)
    except FileNotFoundError:
        return [f"# {path.name} not found"]


def _esc(s: str) -> str:
    return html.escape(s).replace(" ", "&nbsp;")


def _render_side_by_side(left_lines: list[str], right_lines: list[str],
                          left_label: str, right_label: str) -> str:
    """Render two file versions as a side-by-side diff (GitHub-style split view)."""
    sm = difflib.SequenceMatcher(a=left_lines, b=right_lines, autojunk=False)
    rows: list[str] = []

    def _row(kind: str, ln_l: str, line_l: str, sign_l: str,
              ln_r: str, line_r: str, sign_r: str) -> str:
        return (
            f'<div class="diff-row diff-{kind}">'
            f'<div class="diff-lno">{ln_l}</div>'
            f'<div class="diff-sign diff-sign-{sign_l or "ctx"}">{sign_l or "&nbsp;"}</div>'
            f'<div class="diff-code">{_esc(line_l) if line_l else "&nbsp;"}</div>'
            f'<div class="diff-lno">{ln_r}</div>'
            f'<div class="diff-sign diff-sign-{sign_r or "ctx"}">{sign_r or "&nbsp;"}</div>'
            f'<div class="diff-code">{_esc(line_r) if line_r else "&nbsp;"}</div>'
            f'</div>'
        )

    def _hunk_header(i1: int, i2: int, j1: int, j2: int) -> str:
        return (
            f'<div class="diff-hunk-header">'
            f'@@ -{i1 + 1},{i2 - i1} +{j1 + 1},{j2 - j1} @@'
            f'</div>'
        )

    groups = list(sm.get_grouped_opcodes(n=CONTEXT_LINES))
    if not groups:
        return (
            f'<div class="diff-container">'
            f'<div class="diff-header">'
            f'<div class="diff-header-side">{html.escape(left_label)}</div>'
            f'<div class="diff-header-side">{html.escape(right_label)}</div>'
            f'</div>'
            f'<div class="diff-empty">Files are identical.</div>'
            f'</div>'
        )

    for group in groups:
        first_op = group[0]
        last_op = group[-1]
        rows.append(_hunk_header(first_op[1], last_op[2], first_op[3], last_op[4]))

        for tag, i1, i2, j1, j2 in group:
            if tag == "equal":
                for k in range(i2 - i1):
                    rows.append(_row(
                        "equal",
                        str(i1 + k + 1), left_lines[i1 + k], "",
                        str(j1 + k + 1), right_lines[j1 + k], "",
                    ))
            elif tag == "replace":
                left_chunk = left_lines[i1:i2]
                right_chunk = right_lines[j1:j2]
                max_n = max(len(left_chunk), len(right_chunk))
                for k in range(max_n):
                    has_l = k < len(left_chunk)
                    has_r = k < len(right_chunk)
                    rows.append(_row(
                        "replace",
                        str(i1 + k + 1) if has_l else "", left_chunk[k] if has_l else "", "−" if has_l else "",
                        str(j1 + k + 1) if has_r else "", right_chunk[k] if has_r else "", "+" if has_r else "",
                    ))
            elif tag == "delete":
                for k in range(i2 - i1):
                    rows.append(_row(
                        "delete",
                        str(i1 + k + 1), left_lines[i1 + k], "−",
                        "", "", "",
                    ))
            elif tag == "insert":
                for k in range(j2 - j1):
                    rows.append(_row(
                        "insert",
                        "", "", "",
                        str(j1 + k + 1), right_lines[j1 + k], "+",
                    ))

    n_changes = sum(1 for tag, *_ in (op for grp in groups for op in grp) if tag != "equal")
    return (
        f'<div class="diff-container">'
        f'<div class="diff-header">'
        f'<div class="diff-header-side">{html.escape(left_label)}</div>'
        f'<div class="diff-header-side">{html.escape(right_label)}</div>'
        f'</div>'
        f'<div class="diff-body">{"".join(rows)}</div>'
        f'<div class="diff-footer">{n_changes} change hunk(s) · {CONTEXT_LINES} lines of context</div>'
        f'</div>'
    )


def render_diffs_html() -> str:
    """Render the two key diffs and a short explainer."""
    rt = _read(REPO_ROOT / "app_realtime.py")
    vl = _read(REPO_ROOT / "app_voicelive.py")
    ag = _read(REPO_ROOT / "app_agent.py")

    diff_rt_vl = _render_side_by_side(
        rt, vl,
        "app_realtime.py · rung 1 — Azure OpenAI Realtime",
        "app_voicelive.py · rung 2 — Azure Voice Live",
    )
    diff_vl_ag = _render_side_by_side(
        vl, ag,
        "app_voicelive.py · rung 2 — Azure Voice Live",
        "app_agent.py · rung 3 — Voice Live + Foundry Agent",
    )

    return f"""
<div class="diff-section">
  <div class="diff-section-title">
    <span class="diff-step">1</span>
    <span>Realtime → Voice Live</span>
  </div>
  <p class="diff-section-lede">
    The headline diff. <b>Three small changes</b> to the same
    <code>AsyncAzureOpenAI</code> client: a <code>websocket_base_url</code>
    kwarg, a different api-version, and one <code>extra_query</code> key
    (<code>model=</code>) because Voice Live keys off
    <code>&amp;model=</code> not <code>&amp;deployment=</code>.
  </p>
  {diff_rt_vl}
</div>

<div class="diff-section">
  <div class="diff-section-title">
    <span class="diff-step">2</span>
    <span>Voice Live → Voice Live + Foundry Agent</span>
  </div>
  <p class="diff-section-lede">
    Same client, same <code>connect()</code> call. The only new thing is
    the <code>extra_query</code> dict that routes traffic to a hosted
    Foundry Agent instead of a raw model.
  </p>
  {diff_vl_ag}
</div>
"""
