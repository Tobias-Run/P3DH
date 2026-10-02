# KPI-Quellnavigation – Issue #124

Geprüft am 02.10.2026. [Issue #124](https://github.com/Tobias-Run/P3DH/issues/124).

Der Quelllink im KPI-Overview öffnete zwar die richtige Tabelle, scrollte aber nicht dorthin. `jumpToTemplate()` setzte den Filter und suchte sofort die erste Section. `fillTheme()` baut die Tabelle erst nach einem Animation Frame und gegebenenfalls dem Laden der Labels. Zu diesem Zeitpunkt gab es noch keine Section; der Scroll-Aufruf entfiel.

Das produktive HTML unter <https://tobias-run.github.io/P3DH/processed/zweig_a/viewer_json.html> wurde abgerufen und stimmt bytegenau mit `main`, Commit `b22b1b79c1dbe2397c47c5555cc5238a0af071f8`, überein. SHA-256: `733c3a3353b39912367320d15f329293491054dfbbd47c898a1b58bca0de0db6`. Die Browserreproduktion lief lokal mit diesem unveränderten Code und dem Datenbestand.

UniCredit, CON, 31.03.2026, CET1 → 61.00: Bei 1280 und 390 Pixeln Breite wurde der Filter `61.00` gesetzt, doch `main.scrollTop` blieb 0. Nach dem Rendern lag die Quelle rund 1.500 Pixel unterhalb des Viewports. Die Reproduktion verursachte keinen JavaScript-Fehler: Es fehlte eine sichtbare Navigationswirkung.

## Korrektur

Der Sprung wird am zugehörigen Tabellencontainer vorgemerkt und erst nach dessen Rendern ausgeführt. Die exakte Template-ID identifiziert die Zielsection. Ihre Überschrift bekommt Tastaturfokus; der Scroll-Abstand berücksichtigt die tatsächlich gemessene Sticky-Header-Höhe, einschließlich des umgebrochenen Headers auf Mobilgeräten. Nachgeladene Peer-Streifen bewahren den Fokus beim Neuaufbau.

Wird während des Ladens der Filter oder Report gewechselt, verschwindet die Vormerkung mit dem alten DOM. Ein späterer Abschluss scrollt keine neue Ansicht. Es gibt keinen zusätzlichen Datendownload, Timer oder Observer für die Navigation; sie nutzt den vorhandenen Renderabschluss. Der Render-Timer der bisherigen Tabelle bleibt bestehen. Die KPI-Erklärung, Zahlen und Route bleiben verfügbar.

## Validierung

- **1.455 vorhandene Tests bestanden, keine übersprungen**, mit gebauten Zweig-A-Artefakten. Die 16 Scale-Tests aus dem noch offenen PR #123 gehören nicht zu dieser unabhängigen Branch.
- **14 Browserfälle, 24 erfolgreiche Quellsprünge**: Desktop 1280×844 und mobiler Chromium-Viewport 390×844, DE/EN, Klick/Enter und auf Mobilgeräten Touch. Erst verzögert geladene Labels/Peer-Streifen, anschließend warmer Cache und abgeleitete Headroom-KPI.
- Kennzahlensuche: ABN AMRO, Performing-forborne-KPI, beide Quellen **80.00.A und 82.00.A** geprüft, auf Desktop und Mobilgerät. Jeder Link erreicht genau seine eigene sichtbare Tabellenüberschrift.
- Zwei zusätzliche Fälle verwerfen einen ausstehenden Sprung bei Filter- bzw. Reportwechsel. Der spätere Ladeabschluss verändert weder Fenster- noch Report-Scrollposition.
- Fokus, sichtbare Position unterhalb des Headers, aufgeklappter Block, unveränderte Route und fehlende JavaScript-Fehler werden funktional geprüft. Der vollständige Viewercheck umfasst außerdem Benchmark, Zeitreihen, Filter, Peer-Kontext und CSV-Export.
- `scripts/check_viewer_runtime.py` führt die neue Prüfung automatisch aus; sie ist damit Teil der vorhandenen PR-CI. Kein zusätzlicher Produktions-Request oder kompletter Tabellen-Neuaufbau wird für den Sprung eingeführt.

Reproduktion mit installiertem DuckDB, Playwright und Chromium, nach dem bestehenden Zweig-A-Artefaktbau:

```sh
python scripts/check_kpi_navigation.py
python scripts/check_viewer_runtime.py
python -m unittest discover tests -v
```

Die mobile Prüfung simuliert Viewport und Touch in Chromium; sie ersetzt keinen Test auf einem physischen iPhone/Safari. Produktiv wirksam wird die Korrektur nach Merge und Pages-Deployment.
