#!/usr/bin/env bash
# Publish the generated JSON data (processed/zweig_a/data/) to the orphan `data`
# branch, from which jsDelivr serves it to the viewer. The branch is force-pushed
# as a SINGLE fresh commit every time, so neither main nor the data branch
# accumulate history/bloat — the big shard tree never enters main's history.
#
# Viewer reads it in production via:
#   https://cdn.jsdelivr.net/gh/Tobias-Run/P3DH@data/<file>
#
# Usage:  bash scripts/publish_data_branch.sh
set -euo pipefail

REPO_SSH="git@github.com:Tobias-Run/P3DH.git"
KEY="$HOME/.ssh/github_key"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/processed/zweig_a/data"

[ -f "$SRC/index.json" ] || { echo "no data at $SRC — run build_zweig_a_shards.py first"; exit 1; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cp -R "$SRC"/. "$TMP"/
touch "$TMP/.nojekyll"          # so GitHub/jsDelivr serve dotfiles/json verbatim

n_shards=$(find "$TMP/reports" -name '*.json' 2>/dev/null | wc -l | tr -d ' ')
echo "Publishing data branch: index+codebook+benchmark + ${n_shards} shards"

cd "$TMP"
git init -q
git checkout -q -b data
git add -A
GIT_SSH_COMMAND="ssh -i $KEY" \
  git -c user.email="noreply@anthropic.com" -c user.name="P3DH data bot" \
  commit -q -m "data snapshot $(date -u +%FT%TZ)"
GIT_SSH_COMMAND="ssh -i $KEY" git push -f -q "$REPO_SSH" data
echo "✓ pushed orphan branch 'data' (1 commit)"

# Purge jsDelivr's branch cache for the files that change every publish.
for f in index.json codebook.json benchmark.json; do
  curl -fsS "https://purge.jsdelivr.net/gh/Tobias-Run/P3DH@data/$f" >/dev/null \
    && echo "  purged $f" || echo "  purge $f failed (non-fatal)"
done
echo "✓ live at https://cdn.jsdelivr.net/gh/Tobias-Run/P3DH@data/index.json"
