# Sources

Each `sources/<id>.yaml` is one collector input.

| `kind` | Required fields |
| --- | --- |
| `git` | `url`, `default_branch`, optional `path_prefixes` |
| `github_releases` | `github_repo` |
| `rss` | `feed_url` |
| `arxiv` | `arxiv_query` |

`mlir` and `llvm` share `mirror_dirname: llvm-project`.

Large forks (`rocm-llvm`, `mesa`, `onnxruntime`) ship with `enabled: false` until you have disk.

See also [TAXONOMY.md](./TAXONOMY.md) for publication buckets.
