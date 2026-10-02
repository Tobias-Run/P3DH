# UI-Lokalisierung – Issue #127

Geprüft am 02.10.2026. [Issue #127](https://github.com/Tobias-Run/P3DH/issues/127). Die vorherigen sichtbaren deutschen Texte in EN sind bereits im [Einheiten-Audit](../kpi_metric_units/audit_before.txt) reproduziert.

Report-Status, Suchfeld und Hinweis auf unterschiedliche Template-Währungen verwenden jetzt `tr()`. Dasselbe gilt für Compare-Überschrift, Ladezustand, Zellspaltenkopf, Entfernen-Tooltip und Begrenzungsdialog. Benchmark-Perzentilcheckbox, Zahl der Referenzdaten und linke/rechte Randzählungen folgen ebenfalls der aktiven Sprache. Report-Metadaten werden auch in Deutsch lokalisiert.

`bmProfiles()` reichte bisher die vorhandene `note_en` nicht weiter: `mtext()` fiel daher auf Deutsch zurück. Zusätzlich wurden die Profilnamen schon beim ersten Cache-Aufbau in die damalige Sprache aufgelöst und blieben beim Wechsel dort hängen. Der Cache bewahrt nun `label`/`en` und `note`/`note_en`; die Darstellung wählt die aktuelle Sprache. Auch Kennzahlnamen im Ausreißerhinweis folgen `mlabel()`.

## Validierung

- 1.455 vorhandene Tests bestanden, keine übersprungen (vor Kombination mit den 16 zusätzlichen Scale-Tests aus #123).
- 10 neue Browserfälle: EN → DE → EN bei 1280×844 und 390×844, plus je Sprache kalter Report-/Compare-Ladezustand mit kontrolliert zurückgehaltener Shard-Antwort.
- Funktionale Prüfung von Report-Suche, tatsächlichem Report mit mehreren Währungen, Compare mit ausgewählten Reports, Zellkopf und Tooltip sowie tatsächlich ausgelöstem/angenommenem Begrenzungsdialog.
- ESG-, Vergütungs- und Headroom-Profile: alle Profiloptionen, englische/deutsche Erklärung, Perzentil-Label, Referenzdatenzählung und tatsächlich vorhandene Randzählungen werden im DOM geprüft. Die gecachten Profile überleben den Sprachwechsel korrekt.
- Overview-Werte bleiben beim Wechsel exakt gleich. Das CSV-Schema behält Institution/LEI/Datum/Framework und Kennzahl-IDs. Keine JavaScript-Fehler.
- `scripts/check_ui_localization.py` läuft automatisch im vorhandenen Runtimecheck und damit in der PR-CI. Der vollständige Viewercheck umfasst außerdem KPI-Quellnavigation, alle Einheitenprofile, Peer-Kontext, Filter und CSV.

[Browserprotokoll](browser_validation.txt). Mobile Prüfung in Chromium, kein physischer iPhone-/Safari-Test. Originale Institutionsnamen und Offenlegungstexte werden beibehalten. Die Korrektur führt keine neuen Produktions-Requests ein.

## Ergänzung: Templategruppen – Issue #131

[Issue #131](https://github.com/Tobias-Run/P3DH/issues/131): Die zwölf deutschen Gruppenlabels aus dem vorhandenen Codebook werden beim Laden einmal auf englische Übersetzungsschlüssel normalisiert. Die Darstellung verwendet anschließend die aktuelle Sprache. Auch der Auffangblock „Nicht zugeordnet“/„Unassigned“ und die Suchüberschrift „Kennzahlen“/„Metrics“ folgen dem Sprachwechsel. Templatezuordnung, Reihenfolge, Daten und KPI-Auswertung bleiben unverändert. Die Korrektur funktioniert mit veröffentlichten Codebooks ohne Datenneubau oder zusätzliche Requests.

Browserprüfung mit einem echten Jahresbericht, der alle zwölf Gruppen enthält (`213800CBW4NPFP73ZK64`, 2025-12-31, CON): EN → DE → EN bei 1280×844 und 390×844. Alle Gruppenlabels, Suchüberschrift und Filterzählungen geprüft; Sprache und aufgeklappte Gruppen bleiben nach Neuladen erhalten. Ein isolierter unbekannter Zuordnungsschlüssel bestätigt den übersetzten Auffangblock. KPI-Werte bleiben identisch, keine JavaScript-Fehler. Zusätzlich bestehen die zehn bisherigen UI-Browserfälle und alle neun Tests der Templategruppen-Registry. Mobilprüfung in Chromium.
