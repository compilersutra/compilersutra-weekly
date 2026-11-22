---
name: compilersutra-weekly
description: >-
  Author and improve CompilerSutra Weekly editions (compilersutra-weekly repo):
  publication design, briefing cards, featured/deep-dive prose, evidence labels,
  Pages deploy. Use when editing csweekly reporters, edition HTML/MD, weekly.yml,
  docs/PUBLICATION_DESIGN.md, or when the user asks to fix/improve/publish Weekly.
---

# CompilerSutra Weekly (publication runbook)

## Promise (verbatim)

> **CompilerSutra Weekly — Understand what changed in LLVM, GCC, MLIR and GPU compilers, why it matters, and how it works under the hood.**

## Editorial invariant (verbatim)

> **Never let generated explanations claim more than the underlying source evidence establishes.**

**Product rule:** Technical understanding is the product — not the number of commits collected.

## Source of truth

| Doc / code | Role |
| --- | --- |
| `docs/PUBLICATION_DESIGN.md` | Publication architecture + tiers |
| `src/csweekly/brand.py` | Positioning / meta copy |
| `src/csweekly/reporters/publication.py` | Briefing, takeaways, watchlist tiers, lessons |
| `src/csweekly/reporters/index.py` | Issue HTML |
| `src/csweekly/reporters/static/site.css` | Styles (copied to `site/assets` by `csweekly index`) |
| `src/csweekly/ai/writer.py` | Evidence-grounded drafts (no taxonomy filler) |

Repo root: `/home/aitr/projects/compilersutra-weekly`.

Public URL: https://www.compilersutra.com/weekly/

## Page architecture (required order)

1. Hero — title, date window, project chips, positioning lede  
2. **The 3 changes worth knowing** — headline + one-line reason + category (60s scan; no full briefing copy)  
3. **Five-minute briefing** — five stories with what-changed context + source (do not replay Top 3 one-liners)  
4. **Featured** — 2-column cards; evidence + labels in header; scores only inside details  
5. **Under the hood** — one deep dive; sections renumbered sequentially after skips  
6. **Engineering lessons** — concrete patch takeaways (never editorial disclaimers)  
7. **What engineers should watch** — collapsed rows (title / project·component / status); expand for context + limits  
8. Themes / Research / Index  

**Do not add more sections.** Layout is frozen after #003 polish — improve the editorial generation pipeline next. Target: three developments in 60 seconds, then optional 5–20 min.

**Info types (keep distinct):** editorial selection · technical explanation · evidence.

## Watchlist tiers

`needs_inspection` · `potentially_important` · `low_priority` — via `watchlist_bucket()`.

## Layout / visual rules

- Preserve body typography; optimize width/spacing/hierarchy.  
- Prefer fewer colored badges; muted mono labels.  
- Sticky section TOC; deep dive is the visual centerpiece.  
- Do not invent deep-dive answers unsupported by the commit.  

## Hard “do not” rules

1. **No file-path walls** in Implementation / Validation. Explain the mechanism; link the commit.  
2. **No taxonomy filler:** ban “Matters for X compiler engineering” / “Lives in the Middle-end of the pipeline” / “Affects Y lowering / target code generation” as the whole why.  
3. **Path-ground targets.** LLDB/WebAssembly test skips are not AArch64 codegen. Use `path_grounded_targets`.  
4. **Evidence ≠ editorial score.** Show Verified/Source-backed/Inferred/Unverified separately from Editor’s pick /10.  
5. **Deep dive skips empty unknowns.** Do not dedicate a large block to “Previous behavior. Not established…”.  
6. **Every briefing item links** to its featured / dive / signal section.  
7. **Primary commit is a hyperlink** (`dive-commit`), not a bare SHA in a file list.

## Implementation section shape

```
[1–2 sentence mechanism from commit body]

Touches N <surface label> (+X/−Y).

Primary commit: <a href="…"><code>sha</code></a> · +X/−Y
```

Surface labels: e.g. “17 LLDB API test modules”, not 17 absolute paths.

## Coverage tiers

| Level | Meaning | UI |
| --- | --- | --- |
| Featured | Investigated | Full card + optional deep dive |
| Quick signal | Partial evidence | 2–3 sentences |
| Watchlist | Weak evidence | Title + source + uncertainty (dashed) |

Prefer **3 strong featured + 10 signals + 1 excellent dive** over 30 forgettable commit summaries.

## After any presentation change

```bash
cd /home/aitr/projects/compilersutra-weekly
.venv/bin/pip install -e . -q
.venv/bin/csweekly index --reports-dir reports --site-dir site
.venv/bin/python -m pytest tests/test_publication.py tests/test_phase1_editorial.py -q
```

Live site needs **git push + Pages**. Default `GITHUB_TOKEN` pushes do **not** trigger Pages — `weekly.yml` must push with `CSWEEKLY_GITHUB_TOKEN` and/or `gh workflow run pages.yml`.

Verify live:

- https://www.compilersutra.com/weekly/
- https://www.compilersutra.com/weekly/issues/YYYY/YYYY-MM-DD.html

## Findability checklist

- Homepage “This week” shows Edition #NNN with briefing cards  
- Issue hero TOC: Briefing → Featured → Deep dive → Signals → …  
- Commit SHAs are clickable in Featured details + Deep dive + Reproduce  
- Watchlist items are visually distinct (unverified)  

## P2+ (do not block publish)

Diff viewer, pipeline diagram, reproduce commands, cross-week trends — see `docs/PUBLICATION_DESIGN.md`.
