# Phase 1 audit — quality & correctness

Date: 2026-11-14  
Scope: CompilerSutra Weekly site + editorial pipeline (no architecture rewrite).

## Keep

- Static GitHub Pages + `csweekly` Python pipeline
- Changelog JSON as structured source of truth
- Clustering / editorial selection / deep-dive section
- Explore filters (stage / domain / area) as secondary nav
- Subscribe honesty via CompilerSutra Google Form (no fake email inbox on Pages)
- Tagline: **The compiler changes worth understanding.**

## Explicitly closed (unless product reopens)

- **Atom / RSS feed** — intentionally removed from public site; do not restore without a product decision + test rewrite

## Phase 1 editorial bar (shipped)

| Requirement | Mechanism |
| --- | --- |
| Distinct Change vs Why | `ai/writer.py` implication prose; fact-check fails if identical |
| Confidence labels | Verified / Source-backed / Inferred / Unverified chips |
| Featured notes required | `validate.py` requires `confidence` + `factcheck` on deep dive + high signal |
| Analyze before publish | `csweekly publish` runs deterministic evidence→write→factcheck |
| Five-minute briefing | Labeled slots (biggest / GPU / frontend / backend / radar) |
| Deep dive structure | Background → Problem → Previous → Change → Implementation → Example → Impact → Confidence |
| Cadence honesty | Saturday→Friday Asia/Kolkata only (no UTC Fri→Fri copy) |
| No invented IR/benchmarks | Writer limitations + fact-check performance gate |

## Do not touch yet

- React / SPA rewrite
- Email provider / Mailchimp
- Auth, comments, engagement metrics
- Invented benchmarks / IR / assembly
- Homepage “intelligence dashboard” redesign (Phase 2)

## Phase 2 backlog

- Diff explorer UI (files / functions / tests)
- Homepage layout refresh (hero stats, clearer hierarchy)
- Pipeline diagram highlighting affected stage
- Stronger before/after IR when tests provide it

## Phase 3–4

- Benchmark watch, paper→impl links, community corrections
- Pass / backend trackers, learning-ecosystem links
