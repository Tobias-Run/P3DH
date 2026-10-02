# KPI-Einheiten – Issue #126

Geprüft am 02.10.2026. [Issue #126](https://github.com/Tobias-Run/P3DH/issues/126), Umsetzung im [Overview-PR #125](https://github.com/Tobias-Run/P3DH/pull/125).

Die Ausgangsversion `052b14398361e21ab0bceb35649b5463f98a92a4` wurde im lokalen Chromium mit den gebauten Datenartefakten reproduziert: Englisch zeigte UniCredits TREA-Karte mit `Mrd EUR`, die Zeitreihe mit `TREA (Mrd) EUR` und den Benchmark-Kopf mit `Total risk exposure amount (Mrd EUR)`. [Vorher-Nachweis](before.txt).

Die Registry verwendet `Mrd EUR` als kanonische Einheit. Ein gemeinsamer Darstellungsformatter nutzt jetzt die bereits vorhandenen Sprachkürzel: **Englisch `bn EUR`, Deutsch `Mrd. EUR`**. Er gilt für Overview, Benchmark-Köpfe und Einheiten in Kennzahlenerklärungen. Die TREA-/CET1-Zeitreihe nutzt denselben Milliardenformatter. Registry, Werte, EUR-Umrechnung und CSV-Schema werden nicht verändert.

## Prüfung

- 6 Browserfälle: Desktop 1280×844 und Mobilviewport 390×844, jeweils EN → DE → EN. TREA-Karte, TREA-/CET1-Zeitreihe und beide KM1-Betragsspalten im Benchmark enthalten die passende Einheit.
- Alle Overview-KPI-Werte bleiben beim Sprachwechsel exakt gleich. Die englische Übersicht/Zeitreihe enthält kein `Mrd`. Der TREA-Quelllink verweist weiterhin auf 61.00.
- Nach Neuladen bleiben Sprache und Benchmark-Einheiten erhalten. Keine JavaScript-Fehler.
- Vollständiger Viewercheck erfolgreich, einschließlich der 14 Quellnavigation-Fälle mit 24 erfolgreichen Sprüngen aus Issue #124. [Browserprotokoll](browser_validation.txt).
- **1.455 vorhandene Tests bestanden, keine übersprungen.** [Testabschluss](test_suite.txt).

Die neue Prüfung `scripts/check_metric_units.py` ist in `scripts/check_viewer_runtime.py` eingebunden und damit Teil der vorhandenen PR-CI. Mobilprüfung in Chromium; kein physischer Safari-Test. Produktiv nach Merge und Pages-Deployment.
