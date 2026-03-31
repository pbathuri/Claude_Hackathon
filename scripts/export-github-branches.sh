#!/usr/bin/env bash
# Export each remote branch into a separate directory (tracked files only, via git archive).
# Safe: does not modify your current checkout or branch.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

REMOTE="${1:-origin}"
EXPORT_ROOT="${BRANCH_EXPORT_ROOT:-$REPO_ROOT/branch_exports}"

echo "Fetching from $REMOTE ..."
git fetch "$REMOTE" --prune

mkdir -p "$EXPORT_ROOT"
rm -rf "${EXPORT_ROOT:?}"/*
echo "Exporting to: $EXPORT_ROOT"

while IFS= read -r ref; do
  [[ -z "$ref" ]] && continue
  # refs/heads/X on remote -> origin/X
  branch="${ref#refs/remotes/${REMOTE}/}"
  [[ "$branch" == HEAD ]] && continue
  safe="${branch//\//-}"
  dest="$EXPORT_ROOT/$safe"
  mkdir -p "$dest"
  git archive "$REMOTE/$branch" | tar -x -C "$dest"
  echo "  OK  $REMOTE/$branch  ->  $dest"
done < <(git for-each-ref --format='%(refname)' "refs/remotes/${REMOTE}/")

echo "Done. See docs/BRANCH_SNAPSHOTS.md for how to interpret these folders."
