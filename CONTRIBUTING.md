# Contributing

## Source definitions (easiest win)

Add or improve files under `sources/*.yaml`:

- `url` / `github_repo` / `default_branch`
- `path_prefixes` to focus a monorepo slice
- `enabled: true` when the mirror is ready

Open a PR. Keep summaries source-backed — do not paste copyrighted articles wholesale.

## Code

```bash
pip install -e '.[dev]'
pytest -q
```

Use Apache-2.0 headers on new files. Prefer fixtures over live network in tests.
