# Authentication

Git commit collection needs **no** token.

For GitHub Releases / API collectors:

```bash
export CSWEEKLY_GITHUB_TOKEN=ghp_...   # preferred
# or fall back to GITHUB_TOKEN in Actions
```

| Context | Limit (approx.) |
| --- | --- |
| No token | ~60 req/h |
| PAT / fine-grained | ~5000 req/h |
| Actions `GITHUB_TOKEN` | often ~1000 req/h |

Never commit tokens. Tests mock network.
