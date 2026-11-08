# CompilerSutra Weekly

Independent open-source **compiler ecosystem intelligence**.

Tracks LLVM, MLIR, GCC, TVM, IREE, Triton, GPU stacks, and research papers using **git mirrors** plus optional GitHub Releases, RSS, and arXiv — not the CompilerSutra website runtime.

| | |
| --- | --- |
| Window | **Friday → Friday** (UTC, end exclusive) |
| Publish | **Saturday** |
| License | Apache-2.0 |
| CLI | `csweekly` |

CompilerSutra (Docusaurus/Vercel) stays educational. This repo owns collection, processing, reports, and Pages.


## Taxonomy

| Bucket | Sources |
| --- | --- |
| **CPU compilers** | LLVM/Clang, GCC |
| **IR & infra** | MLIR |
| **GPU compilers** | Open source only (ROCm LLVM, Mesa, …) — proprietary CUDA out of scope |
| **AI / DL compilers** | TVM, IREE, Triton, ONNX Runtime (when enabled) |
| **Research** | arXiv |

Details: [docs/TAXONOMY.md](docs/TAXONOMY.md).

## Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
csweekly week --as-of 2026-11-08
csweekly sources
```

## Five-minute demo (no LLVM clone)

```bash
bash scripts/make_fixture_repo.sh
csweekly collect --as-of 2026-11-08 --no-fetch --kind git \
  --repo tests/fixtures/tiny_repo --source llvm
csweekly report --stdout
csweekly index
```

## Weekly production flow

```bash
# optional for GitHub API rate limits
export CSWEEKLY_GITHUB_TOKEN=ghp_...

# light (hosted CI): releases + RSS + arXiv
csweekly run --kind github_releases --kind rss --kind arxiv

# full (self-hosted / Jenkins with disk):
csweekly run --mirrors-dir /var/cache/csweekly/mirrors
```

Artifacts:

- `reports/YYYY/YYYY-MM-DD.md` — Saturday issue  
- `reports/README.md` — archive index  
- `site/` — GitHub Pages payload  

## Add another compiler

1. Copy `sources/llvm.yaml` → `sources/<id>.yaml`
2. Set `url`, `mirror_dirname`, `category`, `enabled: true`
3. Optional: `path_prefixes`, `path_labels`, ignore regexes  
4. Open a PR — no Python required for git sources  

Same pattern for `github_releases`, `rss`, or `arxiv` kinds (`docs/sources.md`).

## Commands

| Command | Role |
| --- | --- |
| `csweekly week` | Show Fri→Fri window + Saturday publish date |
| `csweekly sources` | List enabled sources (`--all` for disabled) |
| `csweekly collect` | Write `data/last_collect.json` |
| `csweekly report` | Render Markdown issue |
| `csweekly index` | Archive + `site/` for Pages |
| `csweekly run` | collect + report + index |

## Auth

See [docs/auth.md](docs/auth.md). Git history needs no token.

## Docs

- [Architecture](docs/architecture.md)
- [Sources](docs/sources.md)
- [Publishing / Pages](docs/publishing.md)
- [Contributing](CONTRIBUTING.md)

## Related

| Project | Role |
| --- | --- |
| CompilerSutra | Education / tutorials |
| CompilerSutraPerf (`csperf`) | Hardware performance measurement |
| **CompilerSutra Weekly** | Ecosystem intelligence (this repo) |
