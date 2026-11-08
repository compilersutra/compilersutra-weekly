# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

from csweekly.config import load_sources

ROOT = Path(__file__).resolve().parents[1]


def test_load_phase1_sources():
    sources = load_sources(ROOT / "sources")
    ids = {s.id for s in sources}
    assert {"llvm", "mlir", "gcc"} <= ids
    enabled = {s.id for s in sources if s.enabled}
    assert "llvm" in enabled and "mlir" in enabled and "gcc" in enabled
