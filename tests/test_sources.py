# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

from csweekly.config import load_sources

ROOT = Path(__file__).resolve().parents[1]


def test_phase1_git_sources_enabled():
    sources = {s.id: s for s in load_sources(ROOT / "sources")}
    for sid in ("llvm", "mlir", "gcc"):
        assert sources[sid].enabled
        assert sources[sid].kind == "git"
    assert sources["mlir"].mirror_dirname == sources["llvm"].mirror_dirname


def test_catalog_has_network_kinds():
    kinds = {s.kind for s in load_sources(ROOT / "sources")}
    assert {"git", "github_releases", "rss", "arxiv"} <= kinds
