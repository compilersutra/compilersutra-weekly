# Architecture

```text
sources/*.yaml  →  collectors (git mirror)  →  JSON stories
                                              ↓
                         processors (dedupe) + analyzers (hotspots)
                                              ↓
                         reporters → reports/YYYY/YYYY-MM-DD.md
```

## Reporting cadence

- **Window:** previous Friday 00:00 UTC → this Friday 00:00 UTC (exclusive end)
- **Publish:** Saturday (date of issue filename)

## Independence

No Python on Vercel. No research API in the Docusaurus build. CompilerSutra only links out to this repo / Pages.
