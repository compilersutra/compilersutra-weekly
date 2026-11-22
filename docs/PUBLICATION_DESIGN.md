# CompilerSutra Weekly — publication design

**Positioning:** Understand what changed in LLVM, GCC, MLIR and GPU compilers, why it matters, and how it works under the hood.

**Editorial invariant:** Never let generated explanations claim more than the underlying source evidence establishes.

**Product:** Technical understanding — not the number of commits collected.

## Audience (priority)

Compiler engineers, GPU developers, LLVM/GCC/MLIR/IREE maintainers, compiler researchers and students. General developers are secondary.

## Issue page structure

Do not add sections. Target: three developments in 60 seconds, then optional 5–20 minutes.

1. **Hero** — edition title, date window, project chips, positioning lede  
2. **The 3 changes worth knowing** — headline, one-line reason, category (no full briefing copy)  
3. **Five-minute briefing** — five stories with what-changed context + source  
4. **Featured engineering changes** — 2-column cards; evidence in header; scores inside details  
5. **Under the hood** — one deep dive; sequential section numbering after skips  
6. **Engineering lessons** — concrete patch takeaways (not disclaimers)  
7. **What engineers should watch** — collapsed title/component/status; expand for context + limits  
8. **Themes / Research / Index** — navigation

### Watchlist tiers

| Bucket | Meaning |
| --- | --- |
| Needs technical inspection | Hot topics, large clusters, higher score |
| Potentially important | Backend/GPU/middle-end interest |
| Low-priority / maintenance | Comments, NFC-ish, thin maintenance |

## Layout notes

- Preserve body typography; optimize width, spacing, hierarchy.  
- Compact sticky section TOC; main content is the focus.  
- Deep dive uses a readable article panel (`max-width` ~48rem).  
- Commit hashes are hyperlinks.  

## Measure (next four editions)

Subscribers · returning readers · reading time · primary-commit clicks · shares · section attention.

## Implementation

- `src/csweekly/reporters/publication.py` — briefing, takeaways, watchlist tiers, lessons  
- `src/csweekly/reporters/index.py` — issue HTML  
- `src/csweekly/reporters/static/site.css` — visual system  
- `src/csweekly/brand.py` — positioning copy  
