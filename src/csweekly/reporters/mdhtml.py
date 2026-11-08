# SPDX-License-Identifier: Apache-2.0
"""Small Markdown → HTML helper for weekly issues (no extra deps)."""

from __future__ import annotations

import html
import re


def markdown_to_html(md: str) -> str:
    lines = md.splitlines()
    out: list[str] = []
    in_ul = False
    in_p = False

    def close_p() -> None:
        nonlocal in_p
        if in_p:
            out.append("</p>")
            in_p = False

    def close_ul() -> None:
        nonlocal in_ul
        if in_ul:
            out.append("</ul>")
            in_ul = False

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            close_p()
            close_ul()
            continue
        if line.startswith("# "):
            close_p(); close_ul()
            out.append(f"<h1>{_inline(line[2:])}</h1>")
            continue
        if line.startswith("## "):
            close_p(); close_ul()
            out.append(f"<h2 id=\"{_slug(line[3:])}\">{_inline(line[3:])}</h2>")
            continue
        if line.startswith("### "):
            close_p(); close_ul()
            out.append(f"<h3>{_inline(line[4:])}</h3>")
            continue
        if line.startswith("> "):
            close_p(); close_ul()
            # gather blockquote
            out.append(f"<blockquote><p>{_inline(line[2:])}</p></blockquote>")
            continue
        if line.startswith("| ") and "|" in line[1:]:
            close_p(); close_ul()
            # skip table rendering complexity — keep as pre for rare tables
            out.append(f"<pre class=\"table-ish\">{html.escape(line)}</pre>")
            continue
        if line.startswith("- "):
            close_p()
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{_inline(line[2:])}</li>")
            continue
        # continuation bullets with leading spaces used in our reports
        if re.match(r"^\s+-\s+", line):
            close_p()
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li class=\"sub\">{_inline(line.strip()[2:])}</li>")
            continue
        close_ul()
        if not in_p:
            out.append("<p>")
            in_p = True
        else:
            out.append("<br/>")
        out.append(_inline(line))
    close_p()
    close_ul()
    return "\n".join(out)


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9\s-]", "", text).strip().lower()
    return re.sub(r"\s+", "-", s)[:80]


def _inline(text: str) -> str:
    # escape first, then re-introduce a few markdown spans
    t = html.escape(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(
        r"\[([^\]]+)\]\((https?://[^)]+)\)",
        r'<a href="\2" rel="noopener noreferrer">\1</a>',
        t,
    )
    return t
