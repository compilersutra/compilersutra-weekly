#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FIX="$ROOT/tests/fixtures/tiny_repo"
rm -rf "$FIX"
mkdir -p "$FIX"
git -C "$FIX" init -q -b main
git -C "$FIX" config user.email "test@compilersutra.com"
git -C "$FIX" config user.name "Weekly Test"
commit() {
  local path="$1" content="$2" msg="$3" when="$4"
  mkdir -p "$FIX/$(dirname "$path")"
  printf '%s' "$content" > "$FIX/$path"
  git -C "$FIX" add "$path"
  GIT_AUTHOR_DATE="$when" GIT_COMMITTER_DATE="$when" git -C "$FIX" commit -q -m "$msg"
}
commit llvm/Old.cpp $'d\n' "llvm: too old" "2026-10-20T12:00:00Z"
commit llvm/Foo.cpp $'a\n' "llvm: improve Foo pass" "2026-10-31T12:00:00Z"
commit mlir/IR/Ops.td $'b\n' "mlir: add Ops" "2026-11-03T12:00:00Z"
commit clang/Bar.cpp $'c\n' "clang: tweak Bar" "2026-11-05T12:00:00Z"
echo "fixture ready: $FIX"
