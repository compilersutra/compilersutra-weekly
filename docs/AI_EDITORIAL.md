# AI technical editorial engine

CompilerSutra Weekly uses AI as a **research and editorial engine**, not a
commit-title summarizer.

```text
Collect → Diff evidence → Write draft → Fact-check → Issue HTML/RSS → QA → Publish
```

Source diffs remain authoritative. AI drafts that fail fact-check are rewritten
deterministically or blocked from sounding like verified performance claims.

## Commands

```bash
# Evidence-backed rewrite of an issue (deterministic; no API key required)
csweekly analyze --changelog reports/2026/2026-11-07.changelog.json --deep-only

# Optional LLM writing (OpenAI-compatible)
export CSWEEKLY_AI_API_KEY=...
export CSWEEKLY_AI_MODEL=gpt-4.1-mini          # optional
export CSWEEKLY_AI_BASE_URL=https://api.openai.com/v1   # optional
csweekly analyze --llm --changelog reports/2026/2026-11-07.changelog.json

# Extra LLM fact-check pass
csweekly analyze --llm --factcheck-llm --changelog ...
```

`csweekly refresh` now routes through the same analyze path (deterministic).

## Pipeline modules

| Module | Role |
| --- | --- |
| `csweekly.ai.evidence` | `git show` facts: body, files, numstat, functions, tests, diff excerpt |
| `csweekly.ai.writer` | Deterministic evidence writer + optional LLM JSON draft |
| `csweekly.ai.factcheck` | Reject unsupported performance / empty evidence |
| `csweekly.ai.pipeline` | analyze_group / analyze_issue_groups + apply to `ChangeGroup` |
| `csweekly.ai.prompts` | System instructions for editor / fact-checker |

## Editorial levels

- `quick_signal` — worth knowing
- `engineering_analysis` — high signal
- `deep_dive` — featured deep dive

## Environment

| Variable | Purpose |
| --- | --- |
| `CSWEEKLY_AI_API_KEY` or `OPENAI_API_KEY` | Enable LLM writer |
| `CSWEEKLY_AI_BASE_URL` / `OPENAI_BASE_URL` | Compatible endpoint |
| `CSWEEKLY_AI_MODEL` | Model id |

Without keys, analyze still improves prose from **commit bodies + diffs + tests**.

## QA artifacts

- `reports/YYYY/YYYY-MM-DD.ai_report.md` — human summary
- `reports/YYYY/YYYY-MM-DD.ai_report.json` — machine audit
- `csweekly validate` checks `deep_dive_notes.factcheck`

## Rule

If evidence is thin: say so.
Never invent IR, assembly, or benchmarks.
