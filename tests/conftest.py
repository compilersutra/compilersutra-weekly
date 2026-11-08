# SPDX-License-Identifier: Apache-2.0
"""Build the tiny git fixture once per session (no nested .git in git)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures" / "tiny_repo"


def _git(fix: Path, *args: str, env: dict | None = None) -> None:
    base = {**os.environ, **(env or {})}
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env=base)


@pytest.fixture(scope="session", autouse=True)
def tiny_repo() -> Path:
    if FIX.exists():
        import shutil

        shutil.rmtree(FIX)
    FIX.mkdir(parents=True)
    _git(FIX, "init", "-b", "main")
    _git(FIX, "config", "user.email", "test@compilersutra.com")
    _git(FIX, "config", "user.name", "Weekly Test")

    def commit(path: str, content: str, message: str, when: str) -> None:
        file = FIX / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")
        _git(FIX, "add", path)
        env = {
            "GIT_AUTHOR_DATE": when,
            "GIT_COMMITTER_DATE": when,
        }
        _git(FIX, "commit", "-m", message, env=env)

    # chronological order matters for git log --since
    commit("llvm/Old.cpp", "d\n", "llvm: too old", "2026-10-20T12:00:00Z")
    commit("llvm/Foo.cpp", "a\n", "llvm: improve Foo pass", "2026-10-31T12:00:00Z")
    commit("mlir/IR/Ops.td", "b\n", "mlir: add Ops", "2026-11-03T12:00:00Z")
    commit("clang/Bar.cpp", "c\n", "clang: tweak Bar", "2026-11-05T12:00:00Z")
    return FIX
