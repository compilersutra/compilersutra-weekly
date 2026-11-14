#!/usr/bin/env bash
# Shallow bare clones for Saturday CI — enough for git log in the closed week.
# Usage: scripts/ci_prepare_mirrors.sh [YYYY-MM-DD-period-start]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MIRRORS="${ROOT}/data/mirrors"
SINCE="${1:-}"
if [[ -z "$SINCE" ]]; then
  SINCE="$(
    cd "$ROOT"
    python3 - <<'PY'
from datetime import date
from csweekly.window import publishable_window
w = publishable_window()
print(w.start.date().isoformat())
PY
  )"
fi

mkdir -p "$MIRRORS"

clone_shallow() {
  local name="$1" url="$2" branch="${3:-main}"
  local dest="${MIRRORS}/${name}"
  if [[ -e "${dest}/HEAD" || -d "${dest}/.git" ]]; then
    echo "mirror ${name}: already present — fetch deepen"
    git -C "$dest" fetch --prune --shallow-since="${SINCE}" origin "+refs/heads/${branch}:refs/heads/${branch}" || \
      git -C "$dest" fetch --prune origin "+refs/heads/${branch}:refs/heads/${branch}" || true
    return 0
  fi
  echo "mirror ${name}: shallow-since=${SINCE} branch=${branch}"
  git clone --bare --filter=blob:none --single-branch --branch "$branch" \
    --shallow-since="$SINCE" "$url" "$dest"
}

clone_shallow llvm-project https://github.com/llvm/llvm-project.git main
clone_shallow gcc https://github.com/gcc-mirror/gcc.git master

echo "mirrors ready under ${MIRRORS} (since ${SINCE})"
