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
# Herkunftsnachweis neben dem Parquet (#20). Der Branch traegt keine Historie:
# ohne Manifest sind zwei Downloads von verschiedenen Tagen nicht unterscheidbar.
[ -f "$ROOT/processed/long/manifest.json" ] && \
  cp "$ROOT/processed/long/manifest.json" "$TMP/state/"
# Mit welchem Codebook der Bestand entstanden ist (#57) — ohne diese Datei
# beginnt jeder frische Runner ohne Gedaechtnis, und die Kopplung greift nie.
[ -f "$ROOT/processed/codebook_fingerprint.txt" ] && \
  cp "$ROOT/processed/codebook_fingerprint.txt" "$TMP/state/"

# Der Branch soll ohne Kenntnis des Code-Repos verstaendlich sein (#20). Bewusst
# OHNE Zahlen — die stehen in state/manifest.json und werden dort gezaehlt; eine
# Zahl in einem handgepflegten Text veraltet.
cat > "$TMP/README.md" <<'DATAREADME'
# P3DH — Datenzweig

Dieser Branch trägt die **erzeugten Daten** des Projekts
[Tobias-Run/P3DH](https://github.com/Tobias-Run/P3DH), nicht den Code.

⚠️ **Kein Verlass auf Dauer:** Der Branch wird bei jedem Pipeline-Lauf
force-gepusht und trägt genau einen Commit. Er hat **keine Historie** — der vorige
Stand ist danach weg. Wer einen bestimmten Stand zitieren oder reproduzieren muss,
nimmt ein **Release-Asset**, nicht diesen Branch.

## Was hier liegt

| Pfad | Inhalt |
|---|---|
| `state/p3dh_long.parquet` | Der Datensatz: eine Zeile je gemeldetem Fakt, DPM-Labels aufgelöst, EUR-normalisiert |
| `state/manifest.json` | Welcher Stand: gezählte Kennzahlen, Commit, Codebook-Fingerabdruck, Schema |
| `state/long_form_raw.csv.gz` | Dieselbe Wahrheit als CSV, vor der Verdichtung |
| `state/filing_indicators.csv.gz` | Coverage-Matrix — welches Template ein Institut als gemeldet deklariert hat |
| `index.json`, `codebook.json`, `benchmark.json`, `reports/` | Zweig A: was der Viewer lädt |

## Bevor Sie damit rechnen

Lesen Sie **[`docs/datensatz.md`](https://github.com/Tobias-Run/P3DH/blob/main/docs/datensatz.md)**
— Schema, Semantik und die dokumentierten Fallen. Mindestens diese drei:

1. `eba_GA:x1` ist die Summenzeile „Total", kein Land. Mitsummieren zählt das
   Gesamtexposure doppelt.
2. „Fehlt" ist nicht „Null". Institute dürfen nach CRR Art. 432 rechtmäßig
   auslassen; `template_reported` sagt, was deklariert wurde.
3. Reporting Framework 4.2 umfasst genau einen Stichtag. Ein Versionsvergleich ist
   damit zugleich ein Zeitvergleich.

## Rechte

Die Offenlegungsdaten stammen von der **Europäischen Bankenaufsichtsbehörde
(EBA)** und sind gesondert zu zitieren; Institutsnamen von GLEIF (CC0). Die
MIT-Lizenz des Code-Repositories deckt diesen Datensatz **nicht** ab. Vollständig:
[`DISCLAIMER.md`](https://github.com/Tobias-Run/P3DH/blob/main/DISCLAIMER.md).

Unabhängiges, nicht-kommerzielles Forschungsprojekt — weder mit der EBA noch mit
GLEIF verbunden. Bereitstellung „as is"; Zahlen vor jeder Verwendung gegen die
offizielle Quelle prüfen.
DATAREADME

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
