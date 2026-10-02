# Reproduktion des eingefrorenen Audits

Datenstand: `f47ef2d32968e59188b4139ede3ccac1d9737f21`, ursprünglicher Detektor: `b22b1b79c1dbe2397c47c5555cc5238a0af071f8`.

Das Repository enthält alle 119 Einzelfallurteile, Messungen, Original-URLs und SHA-256-Nachweise für 280 EBA-ZIPs. Die binären Quelldateien werden nicht mitcommittet. `fetch_snapshot.py` lädt den eingefrorenen Parquet-Snapshot und die Original-ZIPs und bricht ab, falls eine Quelle von ihrem geprüften Hash abweicht. Bereits vorhandene Dateien werden ebenfalls geprüft. Ein geänderter EBA-Stand ersetzt keine Belege unbemerkt.

Vom Repo-Root, mit Python 3 und DuckDB:

```sh
python docs/scale_review_2026-10-01/fetch_snapshot.py
python docs/scale_review_2026-10-01/audit.py
python docs/scale_review_2026-10-01/validate_sources.py
python docs/scale_review_2026-10-01/document.py
python docs/scale_review_2026-10-01/verify_review.py
```

`document.py` enthält die ausdrücklich manuell gepflegten Urteile. `findings.json` enthält davon getrennte Messungen; ein Faktor entscheidet allein nicht, welcher Stichtag falsch ist. `data/rebuilt_flags.csv` ist die byteidentisch reproduzierte ursprüngliche Befundliste. Für deren Neuberechnung den ursprünglichen Detektor aus dem genannten Commit verwenden und `PARQUET` / `OUT` auf den Audit-Snapshot bzw. eine temporäre Datei setzen.

Der aktuelle Detektor wird mit `python scripts/build_report_scale.py` gegen `processed/long/p3dh_long.parquet` gebaut. Für die vollständige Prüfung der Korrektur gegen den exakt geprüften Snapshot siehe [IMPLEMENTATION.md](IMPLEMENTATION.md) und `verify_fix.py`. Aktuelle Meldungen können von diesem Datenstand abweichen; veraltete Sichtprüfungen sind dann kein Bestätigungsbeleg.
