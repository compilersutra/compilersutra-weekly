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

> **CompilerSutra Weekly — Understand what changed in compiler engineering, why it matters, and how it works under the hood.**

## Editorial invariant (verbatim)

> **Never let AI-generated explanations claim more than the underlying source evidence establishes.**

## Source of truth

| Doc / code | Role |
| --- | --- |
| `docs/PUBLICATION_DESIGN.md` | Publication architecture + tiers |
| `src/csweekly/reporters/publication.py` | Briefing cards, headlines, takeaways, path-grounded targets, implementation prose |
| `src/csweekly/reporters/index.py` | Issue HTML |
| `src/csweekly/reporters/static/site.css` | Styles (copied to `site/assets` by `csweekly index`) |
| `src/csweekly/ai/writer.py` | Evidence-grounded drafts (no taxonomy filler) |
| Edition **#003** | Reference design for presentation |

Repo root: `/home/aitr/projects/compilersutra-weekly` (sibling of CompilerSutraPerfTool).

Public URL: https://www.compilersutra.com/weekly/

## Page architecture (required order)

1. Hero — “The week in compiler engineering” + promise  
2. **Five-minute briefing** — editorial cards (not numbered commit dumps)  
3. **Featured** — what changed + why care; compact chips; details expandable  
4. **Engineering deep dive** — 8-section template; do not repeat Featured verbatim  
5. **Worth knowing** — Quick signals vs Watchlist (by evidence confidence)  
6. Themes / Research / Topic index — navigation only  

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
