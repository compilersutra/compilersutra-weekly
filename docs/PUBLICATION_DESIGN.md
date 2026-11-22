# CompilerSutra Weekly — publication design

**Positioning:** Understand what changed in LLVM, GCC, MLIR and GPU compilers, why it matters, and how it works under the hood.

**Editorial invariant:** Never let generated explanations claim more than the underlying source evidence establishes.

**Product:** Technical understanding — not the number of commits collected.

## Audience (priority)

Compiler engineers, GPU developers, LLVM/GCC/MLIR/IREE maintainers, compiler researchers and students. General developers are secondary.

## Issue page structure

1. **Hero** — edition title, date window, project chips, positioning lede  
2. **The 3 changes worth knowing** — highest-priority editorial picks  
3. **Five-minute briefing** — five editorial story cards  
4. **Featured engineering changes** — 2-column cards, expandable details  
5. **Under the hood** — one evidence-bound deep dive  
6. **Engineering lessons** — practical takeaways from featured/dive  
7. **What engineers should watch** — quick signals + tiered watchlist  
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
