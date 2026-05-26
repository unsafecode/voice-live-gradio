"""Render the side-by-side diffs between the three rung apps for the UI's "View the diff" tab."""
from __future__ import annotations

import difflib
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

RUNGS = [
    ("app_realtime.py",  "rung 1 — Azure OpenAI Realtime"),
    ("app_voicelive.py", "rung 2 — Azure Voice Live (the punchline)"),
    ("app_agent.py",     "rung 3 — Voice Live + Foundry Agent"),
]


def _read(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines(keepends=False)
    except FileNotFoundError:
        return [f"# {path.name} not found"]


def _html_diff(left: tuple[str, str], right: tuple[str, str]) -> str:
    left_name, left_label = left
    right_name, right_label = right
    left_lines = _read(REPO_ROOT / left_name)
    right_lines = _read(REPO_ROOT / right_name)
    differ = difflib.HtmlDiff(wrapcolumn=72, tabsize=4)
    table = differ.make_table(
        left_lines, right_lines,
        fromdesc=left_label, todesc=right_label,
        context=True, numlines=1,
    )
    # difflib's default HTML uses inline class names that look terrible without their stylesheet;
    # inject a compact stylesheet so the diff is readable in Gradio.
    style = """
<style>
.diff_table { font-family: 'SFMono-Regular','Consolas','Liberation Mono',Menlo,monospace;
              font-size: 12px; border-collapse: collapse; width: 100%; margin: 6px 0 24px; }
.diff_table td { padding: 2px 6px; vertical-align: top; white-space: pre-wrap; word-break: break-all; }
.diff_header { background: #eef; color: #333; font-weight: 600; }
.diff_next { background: #f6f8fa; color: #888; }
.diff_add { background: #d4edda; color: #155724; }
.diff_chg { background: #fff3cd; color: #856404; }
.diff_sub { background: #f8d7da; color: #721c24; }
table.diff thead th { background: #0078D4; color: white; padding: 6px; }
</style>
"""
    return style + table


def render_diffs_html() -> str:
    """Render the two key diffs and a short explainer."""
    diff_rt_vl = _html_diff(("app_realtime.py", "rung 1 — Azure OpenAI Realtime"),
                            ("app_voicelive.py", "rung 2 — Azure Voice Live"))
    diff_vl_ag = _html_diff(("app_voicelive.py", "rung 2 — Azure Voice Live"),
                            ("app_agent.py",    "rung 3 — Voice Live + Foundry Agent"))

    return f"""
<h3>① Azure OpenAI Realtime → Azure Voice Live</h3>
<p style="color:#555;">The headline diff. <b>Three small changes</b> to the same <code>AsyncAzureOpenAI</code> client:
the <code>websocket_base_url</code> kwarg, the api-version (Realtime is still on preview because
<code>openai 2.x</code> hasn't adopted the GA <code>/openai/v1/realtime</code> path yet; Voice Live is
GA on <code>2025-10-01</code>), and one <code>extra_query</code> key (<code>model=</code>) because
Voice Live keys off <code>&amp;model=</code> not <code>&amp;deployment=</code>.</p>
{diff_rt_vl}

<h3>② Azure Voice Live → Voice Live + Foundry Agent</h3>
<p style="color:#555;">Same client. Same <code>connect()</code> call. The only new thing is the
<code>extra_query</code> dict that routes traffic to a hosted Foundry Agent
instead of a raw model.</p>
{diff_vl_ag}
"""


# Strip ANSI / control chars defensively if any sneak in via file reads
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(s: str) -> str:
    return _ANSI_RE.sub("", s)
