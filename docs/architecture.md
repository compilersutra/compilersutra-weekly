# Architecture

```text
sources/*.yaml
    │
    ▼
pipeline.collect_all
    ├─ git_mirror        (persistent clones; Sat→Fri Asia/Kolkata git log)
    ├─ github_releases   (optional CSWEEKLY_GITHUB_TOKEN)
    ├─ rss_feed
    └─ arxiv_api
    │
    ▼
processors.dedupe + analyzers.hotspots
    │
    ▼
reporters.markdown → reports/YYYY/YYYY-MM-DD.md
reporters.index    → reports/README.md + site/
```

## Cadence

- Window: previous Friday 00:00 UTC → this Friday 00:00 UTC (end exclusive)
- Publish: Saturday

## Independence

No Python on Vercel. No research workers in Docusaurus. The education site only links out.
