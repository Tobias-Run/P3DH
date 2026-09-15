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
