# CompilerSutra Weekly — publication design

**Promise:** Understand what changed in compiler engineering, why it matters, and how it works under the hood.

**Editorial invariant:** Never let generated explanations claim more than the underlying source evidence establishes.

Edition **#003** is the reference presentation for future issues. Collection, freeze, and evidence packs stay unchanged; the HTML/Markdown surface is the publication layer.

## Page architecture

1. Hero — week framing + promise  
2. Five-minute briefing — editorial cards (headline, summary, takeaway, evidence)  
3. Featured developments — what changed + why care; compact chips; details expandable  
4. Engineering deep dive — 8-section template (skip unknown previous-behavior filler)  
5. Worth knowing — Quick signals vs Watchlist (evidence confidence)  
6. Themes / research / topic index — navigation only  

## Coverage tiers

| Level | Meaning | Presentation |
| --- | --- | --- |
| Featured | Significant, investigated | Full story + optional deep dive |
| Quick signal | Relevant, partial evidence | 2–3 sentences |
| Watchlist | Interesting, weak evidence | Title + source + uncertainty |

## Editorial ranking vs evidence

- **Editorial score** (shown as Editor's pick): significance 30% · impact 25% · novelty 20% · breadth 15% · evidence 10%. Triage aid only.  
- **Evidence confidence:** Verified · Source-backed · Inferred · Unverified — independent of score.

## Implementation

- `csweekly.reporters.publication` — briefing cards, headlines, takeaways, path-grounded targets  
- `csweekly.reporters.index` — issue HTML  
- `csweekly.ai.writer` — implication prose without taxonomy filler  
- Future editions inherit this when `csweekly publish` / `csweekly index` rebuild the site  

## Roadmap (not all shipped)

- **P0** Editorial quality — largely this design  
- **P1** Reading experience — cards, compact metadata, expandable details  
- **P2** Diff viewer, pipeline diagram, reproduce commands  
- **P3** Cross-week trends / architecture intelligence  
