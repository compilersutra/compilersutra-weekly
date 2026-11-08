# Source configuration

Each `sources/<id>.yaml` describes one feed into the weekly.

| Field | Purpose |
| --- | --- |
| `id` | Stable id (`llvm`, `gcc`, …) |
| `category` | Report section key (`llvm`, `mlir`, `gcc`, `tvm`, `gpu`, …) |
| `kind` | `git` today; later `rss` / `arxiv` / `github` |
| `url` | Clone URL |
| `mirror_dirname` | Folder under `data/mirrors/` |
| `path_prefixes` | Keep commits that touch these paths |
| `path_labels` | Prefix titles when paths match |
| `enabled` | `false` until you are ready to fetch |

MLIR shares the LLVM mirror via the same `mirror_dirname: llvm-project`.
