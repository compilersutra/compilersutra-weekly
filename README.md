# CompilerSutra Weekly

Independent open-source **compiler ecosystem intelligence**.

Tracks what landed across LLVM, MLIR, GCC (and later TVM / GPU stacks) using **local git mirrors**, not the CompilerSutra website runtime.

| | |
| --- | --- |
| Window | **Friday → Friday** (UTC, end exclusive) |
| Publish | **Saturday** |
| License | Apache-2.0 |
| Site link only | [compilersutra.com](https://www.compilersutra.com/) → Weekly (external) |

CompilerSutra (Docusaurus/Vercel) stays a learning site. This repo owns collection, processing, and reports.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'

csweekly week --as-of 2026-11-08
# window: 2026-10-30 → 2026-11-06 (UTC)
# publish: 2026-11-07 (Saturday)
```

### Demo with the tiny fixture (no LLVM clone)

```bash
bash scripts/make_fixture_repo.sh
csweekly collect --as-of 2026-11-08 --no-fetch \
  --repo tests/fixtures/tiny_repo --source llvm \
  --out data/last_collect.json
csweekly report --in data/last_collect.json --stdout
```

### Real mirrors (Phase 1)

First fetch is large (esp. `llvm-project`). Keep mirrors under `data/mirrors/` on a persistent disk (Jenkins / self-hosted runner).

```bash
# optional: authenticated GitHub API later
export CSWEEKLY_GITHUB_TOKEN=ghp_...   # never commit

csweekly run --as-of 2026-11-08 --mirrors-dir data/mirrors
# → reports/2026/2026-11-08.md
```

`mlir.yaml` reuses the **same** `llvm-project` mirror and keeps commits that touch `mlir/`.

## Add another compiler

Copy `sources/llvm.yaml` → `sources/<id>.yaml`, set `url`, `default_branch`, optional `path_prefixes`, set `enabled: true`. Same collector — no new Python required for git-tracked projects.

See [docs/architecture.md](docs/architecture.md) and [docs/sources.md](docs/sources.md).

## Layout

```text
sources/          # contributor-friendly source definitions
src/csweekly/     # collectors / processors / analyzers / reporters
data/mirrors/     # persistent git mirrors (gitignored)
reports/YYYY/     # Saturday Markdown issues
```

## Auth

Git commit collection needs **no** token. Optional `CSWEEKLY_GITHUB_TOKEN` is for future PR/release API collectors. Tests use fixtures only.

## CI

- GitHub Actions: `.github/workflows/weekly.yml` (Saturday)
- Jenkins: `Jenkinsfile` (optional)

## Related projects

- **CompilerSutra** — education / tutorials  
- **CompilerSutraPerf (`csperf`)** — hardware performance measurement  
- **CompilerSutra Weekly** — ecosystem intelligence (this repo)
