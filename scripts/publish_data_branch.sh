#!/usr/bin/env bash
# Publish the generated JSON data (processed/zweig_a/data/) to the orphan `data`
# branch, from which jsDelivr serves it to the viewer. The branch is force-pushed
# as a SINGLE fresh commit every time, so neither main nor the data branch
# accumulate history/bloat — the big shard tree never enters main's history.
#
# The branch also carries the pipeline STATE under state/ (long form + coverage
# matrix, gzipped, plus the Zweig-B parquet). That state is what makes a stateless
# run possible: restore it with scripts/fetch_state.sh, and only the new
# submissions have to be downloaded and parsed. It doubles as the public download
# of the analytics layer.
#
# Viewer reads it in production via:
#   https://cdn.jsdelivr.net/gh/Tobias-Run/P3DH@data/<file>
#
# Auth: uses $P3DH_PUSH_URL if set (CI: https URL carrying a token), else the
# local SSH key.
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

# --- pipeline state (optional: only what exists locally is published) ----------
mkdir -p "$TMP/state"
for f in "$ROOT/processed/long_form_raw.csv" "$ROOT/processed/filing_indicators.csv"; do
  [ -f "$f" ] || continue
  gzip -c "$f" > "$TMP/state/$(basename "$f").gz"
done
[ -f "$ROOT/processed/long/p3dh_long.parquet" ] && \
  cp "$ROOT/processed/long/p3dh_long.parquet" "$TMP/state/"
# Mit welchem Codebook der Bestand entstanden ist (#57) — ohne diese Datei
# beginnt jeder frische Runner ohne Gedaechtnis, und die Kopplung greift nie.
[ -f "$ROOT/processed/codebook_fingerprint.txt" ] && \
  cp "$ROOT/processed/codebook_fingerprint.txt" "$TMP/state/"

n_shards=$(find "$TMP/reports" -name '*.json' 2>/dev/null | wc -l | tr -d ' ')
state_sz=$(du -sh "$TMP/state" 2>/dev/null | cut -f1)
echo "Publishing data branch: index+codebook+benchmark + ${n_shards} shards + state (${state_sz})"

cd "$TMP"
git init -q
git checkout -q -b data
git add -A
git -c user.email="noreply@anthropic.com" -c user.name="P3DH data bot" \
  commit -q -m "data snapshot $(date -u +%FT%TZ)"

if [ -n "${P3DH_PUSH_URL:-}" ]; then
  git push -f -q "$P3DH_PUSH_URL" data
else
  GIT_SSH_COMMAND="ssh -i $KEY" git push -f -q "$REPO_SSH" data
fi
echo "✓ pushed orphan branch 'data' (1 commit)"

# Purge jsDelivr's branch cache for the files that change every publish.
for f in index.json codebook.json benchmark.json; do
  curl -fsS "https://purge.jsdelivr.net/gh/Tobias-Run/P3DH@data/$f" >/dev/null \
    && echo "  purged $f" || echo "  purge $f failed (non-fatal)"
done
echo "✓ live at https://cdn.jsdelivr.net/gh/Tobias-Run/P3DH@data/index.json"
