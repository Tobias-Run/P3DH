# Umsetzung von Issue #122

Stand: 02.10.2026 UTC. [Issue #122](https://github.com/Tobias-Run/P3DH/issues/122).

Alle 119 bestehenden aktiven Scale-Befunde wurden geprüft. Die Korrektur verändert Warnungen und die daraus abgeleitete Vergleichbarkeit, keine gemeldeten Zahlen. Alpha Bank S.A., CR3 23.00 vom 30.06.2025 bleibt mit der Hypothese Faktor 10^6 gewarnt. Details und Originalbelege stehen im [Audit](REPORT.md) und in den [119 Einzelfallurteilen](review_119_findings.csv).

## Vollständiger Vorher/Nachher-Vergleich

Daten-Snapshot `f47ef2d32968e59188b4139ede3ccac1d9737f21`, Parquet-SHA-256 `8cc95fa2dd4a7d08c7502fb9e433bbe4f311d51ee50a17533730ee9db9fc6cdf`. Ausgangscode `b22b1b79c1dbe2397c47c5555cc5238a0af071f8`. 2.295.224 Fakten, 882 Reports mit Fakten. Im Viewer zusätzlich ein Report ohne Fakten; 2.295.189 platzierte Fakten.

| Kategorie | Vorher | Nachher |
|---|---:|---:|
| Report: skaliert | 54 | 54 |
| Report: Verdacht | 17 | 17 |
| Report: unauffällig | 811 | 811 |
| Template: skaliert | 48 | 46 |
| Template: offener Verdacht | 0 | 1 |
| Aktive Befunde | 119 | 118 |
| CSV-Zeilen insgesamt | 930 | 929 |

Genau zwei neue Warnungsschlüssel und drei weggefallene Schlüssel:

- **K&H 41.00:** Dezemberwarnung entfernt; Juni mit `zu_gross`, Faktorhypothese 10^6. Juni enthält 3,117 Billiarden EUR bei 7,592 Mrd. TREA; Dezember 3,273 Mrd. EUR ist plausibel.
- **Citibank Europe 68.00:** Dezemberwarnung entfernt; Juni mit `zu_gross`, Faktorhypothese 10^3. Der im Dezember wiederholte Juniwert belegt den Richtungsfehler.
- **BBVA 83.01.C, Juni:** Warnung entfernt. 15 gleiche fachliche Datenpunkte liegen auf derselben Skala; die veränderte Zellzusammensetzung hatte einen Populationssprung erzeugt.

Die 35 gut gestützten Templatebefunde bleiben erhalten. **Neun Teilbefunde mit 261 Datapoint-/Dimensionsmasken** werden enger beschrieben: Rabobank und BRD nur KM1-Liquidität/Funding, Bank Austria nur die Vorperiodenspalte, weitere gemischte Bereiche bei BPCE, BBVA, Société générale und BNP. Rabobanks Faktorhypothese ist 10^6; Société générale 27.02.B enthält 10^6 und 10^9 und erhält deshalb keinen Einzelmultiplikator.

UniCredit Czech/Slovakia 29.02.A bleibt `verdacht`, Richtung/Umfang offen und Faktor leer: dimensionslose Risikogewichte wurden als monetär typisiert und FX-umgerechnet. Diese Werte werden aus direkten monetären Skalenvergleichen ausgeschlossen. Die fachlich richtige Taxonomie-/Parserkorrektur bleibt offen; Rohwerte und bestehende Normierung werden nicht automatisch verändert. Auch die 17 Reportverdachte bekommen keinen scheinbar bestätigten Faktor. Bei MERKANTI und BANCA PROMOS ist die geringe Institutsgröße eine plausible Erklärung.

[scale_diff_122.json](scale_diff_122.json) enthält **jede geänderte vollständige CSV-Zeile**, die exakten hinzugekommenen/weggefallenen Schlüssel, alle Zählungen und den IRRBB-Vergleich.

## Entscheidungsverfahren und Grenzen

1. Die bestehende Reportheuristik bleibt bestehen. Auf Templateebene wählen Populationssprünge Kandidaten aus; sie bestätigen keinen Fehler.
2. `scripts/scale_evidence.py` vergleicht gleiche Entity/Scope, Template, Zeile, Spalte, offene Dimensionen und Datapoint. Mehrdeutige Duplikate, Nullwerte und Vorzeichenwechsel liefern keine zuverlässige Vergleichsevidenz. Negative Werte gleichen Vorzeichens werden berücksichtigt.
3. Direkte Log-Verhältnisse ab 2,5 Größenordnungen nominieren Teilfehler. Mindestens fünf betroffene Paare erhalten eine Teilmaske, selbst wenn der Gesamtmedian normal ist. Ein einheitlicher Templatebruch erfordert mindestens 70 % verschobene Paare, gleiche Richtung und mindestens 70 % nahe dem vermuteten Exponenten (±0,5 Größenordnungen). Ein automatischer Klein-Skalenbefund braucht zusätzlich mindestens zehn Paare, eigenen Populationsversatz ≤−1,5 und Referenzversatz >−1. Er bleibt als direkte Vergleichshypothese erkennbar.
4. Ohne geeignete Vergleichsbasis bleibt der Kandidat Verdacht. Bei mindestens fünf vergleichbaren Paaren ohne Sprung entfällt das Sprungsignal; das bestätigt nicht ungeprüfte oder unbesetzte Zellen. Der größte eigene Stichtag wird nicht automatisch als korrekt angesehen.
5. Für die 48 geprüften Sonderfälle ist die fachliche Sichtprüfung explizit in `codebook/scale_reviews.json` hinterlegt. Bestätigung, Ablehnung, Richtungswechsel und Teilmasken gelten nur, wenn **alle** SHA-256-Fingerabdrücke der geprüften monetären Reports passen. Sie umfassen Rohwert, EUR-Wert, Quellfilename, Währung, FX, Datentyp, Labels, Framework und Zellidentität einschließlich Duplikaten. Das schützt auch die Größenanker und historische Referenzen. Beide Fehlerrichtungen sind darstellbar; die beiden belegten Übergrößen werden durch diese Sichtprüfung richtig zugeordnet.
6. Ändern sich Quellen oder Interpretation, wird die Sichtprüfung als `veraltet` in `processed/scale_review_status.json` geführt. Ein vorhandener Kandidat wird zu einem richtungs- und faktoroffenen Verdacht herabgestuft. Alte Ablehnungen oder Datumsverschiebungen werden nicht erneut angewendet. Eine fehlende automatische Kandidatur wird dadurch nicht als neu bestätigter Fehler erfunden.

Die Methode ist keine vollständige Erkennung aller denkbaren Einheitenfehler. Neue Sonderfälle, fehlende Referenzen oder unbesetzte Datenpunkte können eine erneute Sichtprüfung benötigen. Faktoren sind Hypothesen; weder `decimals` noch der Detektor multiplizieren Daten. Die Sichtprüfung belegt nicht für jede Bank eine unabhängig veröffentlichte PDF-Einheit.

## Verwendung im Viewer und in Auswertungen

`scale_flags.csv` ergänzt Richtung, Umfang, Referenz, Belegstatus, begründete Faktorhypothesen und genaue Zellmasken. `index.json` erhält je Template einen eigenen Status; der zuerst gelesene Faktor kann nicht auf andere Templates übergreifen. Der Viewer zeigt diese Informationen auf Deutsch und Englisch. Der CSV-Export enthält die strukturierten Warnungen, einschließlich Teilmasken und Referenzen.

Größenbalken, Betragsverteilungen, Betragsperzentile und Betrags-Ausreißergrenzen verwenden nur vergleichbare Quellzellen. Das gilt auch für absolute Überblickskennzahlen. Plausible Kapital-/TREA-Werte bei isoliertem Liquiditätsfehler bleiben nutzbar; betroffene Liquiditätsbeträge werden ausgeschlossen. Der Viewer verwendet konservativ Zeilen-/Spaltenmasken, während die Befund-CSV zusätzlich Datapoints und offene Dimensionen bewahrt. Unbekannter Umfang wird nicht als saubere Zelle ausgelegt. Die Tabellen behalten die gemeldeten Werte und ihre Warnungen.

Quoten bleiben nur bei derselben Skala in Zähler und Nenner vergleichbar. Die neue Anzeige und der Export erklären diese Bedingung; eine pauschale Gültigkeitsaussage entfällt. Die bisherigen Quoten werden nicht neu skaliert oder stillschweigend ersetzt.

IRRBB berücksichtigt nun bestätigte Fehler in 68.00 oder im tatsächlichen Tier-1-Nenner. Isolierte KM1-Liquiditätsfehler sperren den Nenner nicht. Gegen die alte Datei ändern sich **30 von 1.980 Zeilen** ausschließlich bei `vorbehalt` und den SOT-Urteilen: Kuntarahoitus, Euroclear, Raiffeisen Bank International, Citibank und Société générale, jeweils sechs Szenarien. Zahlen und berechnete Quotienten bleiben identisch. Citibank Juni wechselt von `unplausibel` zu `skala`; die vier anderen Templatefehler bekommen erstmals den erforderlichen Vorbehalt. Keine verbleibende SOT-Überschreitung wird durch eine Wertkorrektur erfunden.

Die Zell-Populationsprüfung behält ihren bisherigen Ausschluss bestätigter Reportwarnungen. Footprint berücksichtigt seine eigenen CCyB-Templates. Diese Korrektur weitet deren fachlichen Geltungsbereich nicht auf fachfremde Teilmasken aus.

## Validierung und Wiederholung

- **1.471 Tests bestanden, keine übersprungen**, mit frisch gebauten Zweig-A-Artefakten. Darunter 16 neue Tests für Zellzusammensetzung, Dimensions-/Datapointidentität, Vorzeichen, Mischfehler, Richtung, veränderte Quellen/FX/Labels, Masken und Verbraucher.
- **12 unabhängige Audit-Replay-Checks bestanden**, alle **281 Binärdateien** (Parquet + 280 Original-ZIPs) gegen gespeicherte SHA-256 geprüft.
- `verify_fix.py` prüft die gesamte Befundliste, alle 48 gültigen Sichtprüfungen, neun Teilmasken, Faktorunsicherheit, exakte neue/entfernte Schlüssel und jede IRRBB-Zeile.
- Vollständige Neuberechnung von `scale_flags.csv` ist byteidentisch wiederholbar. Shard-Bau: **0 von 883 Reportshards geändert**, Zahlen unverändert.
- Vollständige Chromium-Laufzeitprüfung: Reportdarstellung, Kennzahltexte, Benchmark, Peer-Kontext, Zeitreihen, Navigation, Balken, Filterzustand und CSV-Export. Teilmasken und ungeeignete Referenzmaxima werden funktional geprüft. Der Test bewahrt Balkenregeln und Exportregeln getrennt, damit keine Testantwort überschrieben wird.
- Gezielte zusätzliche Browserprüfung: neun Fälle × zwei Viewports (1280×800 und 390×844) × Deutsch/Englisch = **36 Sprach-/Ansichtsprüfungen**. Sie prüft tatsächlich gerenderte Warnungen sowie CSV-Inhalte und Rabobanks TREA-/Liquiditätsregeln. Mobile Viewportsimulation ist kein Test auf physischem iPhone/Safari.
- Pipeline-Reihenfolge: **62 Abhängigkeiten geprüft**. PR-CI baut die Befunde vor den Shards, testet ohne Artefakt-Auslassungen und führt beide Browserprüfungen aus. Die Produktionspipeline committet Befunde und Reviewstatus zusammen.
- Zusätzliche ausführliche Warnmetadaten kosten **4.383 Bytes gzip** im vorhandenen Index (52.614 Bytes gzip insgesamt); dafür entstehen keine zusätzlichen Requests. Kein veränderter Zahlen-Shard wird geladen. Das ist eine Payloadmessung, keine neue Geschwindigkeitsmessung auf produktivem Pages.

Vom Repo-Root nach dem Download des eingefrorenen Audits ([REPRODUCE.md](REPRODUCE.md)):

```sh
# Den geprüften Parquet-Snapshot unter processed/long/p3dh_long.parquet bereitstellen.
python scripts/build_report_scale.py
python scripts/build_irrbb_sensitivity.py
python scripts/build_zweig_a_shards.py
python scripts/build_dataset_manifest.py
python -m unittest discover tests -v
python scripts/check_pipeline_order.py
python scripts/check_viewer_runtime.py
python scripts/check_scale_runtime.py
python docs/scale_review_2026-10-01/verify_fix.py
```

Für `check_viewer_runtime.py` wird Chromium aus der CI-Playwright-Installation verwendet; bei lokal vorhandenem System-Chromium kann `runtime.CHROMIUM` vor dem Aufruf auf dessen Pfad gesetzt werden. Coverage-Datei und Codebook werden wie im CI-Workflow bereitgestellt. Das produktive Deployment erfolgt nach geprüftem Merge über die bestehende Pipeline.
