# Phase 1 audit — quality & correctness

Date: 2026-11-10  
Scope: CompilerSutra Weekly site + Issue `#001` pipeline (no architecture rewrite).

## Keep

- Static GitHub Pages + `csweekly` Python pipeline
- Changelog JSON as structured source of truth
- Clustering / editorial selection / deep-dive section
- Explore filters (stage / domain / area) as secondary nav
- Atom feed + subscribe honesty (no fake email)

## Fix now (done / in progress)

| Issue | Root cause | Fix |
| --- | --- | --- |
| `BackendBackendCPU`-style noise | Badges + meta repeated same dims; chips lacked separators | Independent tax chips (`project/stage/domain/target`) via `taxonomy_ui.py` |
| CPU on every frontend/debugger story | Default `llvm/gcc → CPU` | Evidence-gated CPU in `taxonomy.py` |
| 9 high-signal vs 6 cards | Deep dive counted in total; homepage sliced to 6 | Explicit “Showing N of M” + exclude featured from grid |
| Archive date / window clutter | ISO + long window string | Human date (`7 Nov 2026`); cleaner row meta |
| Homepage nav duplication | Subnav + pipeline + HW grid + topic buckets | Homepage: hero → deep dive → highlights → compact explore |
| Thin technical copy | Subject-only explain | Mirror `git log`/`show` enrichment into deep-dive notes |

## Do not touch yet

- React / SPA rewrite
- Email provider
- Auth, comments, engagement metrics
- Invented benchmarks / IR / assembly

## Phase 2 backlog

- Diff explorer UI (files / functions / tests)
- Pipeline diagram highlighting affected stage
- Stronger before/after IR when tests provide it

## Phase 3–4

- Benchmark watch, paper→impl links, community corrections
