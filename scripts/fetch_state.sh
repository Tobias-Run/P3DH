#!/usr/bin/env bash
# Restore the pipeline state published by scripts/publish_data_branch.sh.
#
# The state (long form + coverage matrix + Zweig-B parquet) lives on the orphan
# `data` branch under state/ and is NOT kept on main — it is large and fully
# regenerable. Restoring it lets any machine (a fresh CI runner, a reinstalled
# laptop) continue incrementally instead of re-downloading and re-parsing the
# whole corpus from EDAP.
#
# Served straight from the branch (not jsDelivr: these files are larger than the
# CDN comfortably caches, and we want the exact current commit, not a cached one).
#
# Usage:  bash scripts/fetch_state.sh
set -euo pipefail

BASE="https://raw.githubusercontent.com/Tobias-Run/P3DH/data/state"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$ROOT/processed/long"

fetch() {  # <remote-name> <local-path> [gz]
  local url="$BASE/$1" dest="$2"
  echo -n "  $1 … "
  if [ "${3:-}" = "gz" ]; then
    if curl -fsSL --max-time 300 "$url" | gunzip > "$dest.tmp" 2>/dev/null; then
      mv "$dest.tmp" "$dest"; echo "✓ $(du -h "$dest" | cut -f1)"
    else
      rm -f "$dest.tmp"; echo "✗ (fehlt auf dem data-Branch)"; return 1
    fi
  else
    if curl -fsSL --max-time 300 -o "$dest.tmp" "$url"; then
      mv "$dest.tmp" "$dest"; echo "✓ $(du -h "$dest" | cut -f1)"
    else
      rm -f "$dest.tmp"; echo "✗ (fehlt auf dem data-Branch)"; return 1
    fi
  fi
}

echo "Restoring pipeline state from the data branch:"
rc=0
fetch long_form_raw.csv.gz    "$ROOT/processed/long_form_raw.csv"      gz || rc=1
fetch filing_indicators.csv.gz "$ROOT/processed/filing_indicators.csv" gz || rc=1
fetch p3dh_long.parquet       "$ROOT/processed/long/p3dh_long.parquet"    || rc=1

if [ "$rc" -ne 0 ]; then
  echo "⚠ Teile des Zustands fehlen — ein voller Rebuild (download + parse --full) wäre nötig."
  exit "$rc"
fi
echo "✓ Zustand wiederhergestellt"
