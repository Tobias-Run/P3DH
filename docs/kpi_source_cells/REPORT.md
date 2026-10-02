# Exakte KPI-Quellzellen – Issue #129

Geprüft am 02.10.2026. [Issue #129](https://github.com/Tobias-Run/P3DH/issues/129).

Der bestehende Quellsprung erreichte die Template-Überschrift. Er nimmt jetzt zusätzlich die Kennzahl-ID aus dem Link mit. Die Registry identifiziert Template, Zeile und Spalte; die Markierung stimmt außerdem mit dem tatsächlich angezeigten Rohwert und Dimensionsschnitt überein. Die umgerechnete bzw. gerundete Zeichenkette wird nicht als Suchschlüssel verwendet.

Direkte KPI: eine vorhandene Wertzelle wird blau eingerahmt, fokussiert und vertikal/horizontal sichtbar gemacht. Berechnete KPI: die vorhandenen Quellzellen im gewählten Template werden markiert; die Erläuterung benennt sie als Quellen. Der Ergebniswert wird nicht als gemeldete Zelle ausgegeben. Bei Headroom sind beispielsweise die Total-Capital-Quote und die Gesamtanforderung markiert.

Fehlende oder widersprüchliche Quellwerte erzeugen keine falsche Markierung; der Sprung erreicht dann die Überschrift mit einem Hinweis. Ein zur Quelle gehörender Dimensionsschnitt wird ausgewählt. Beim manuellen Wechsel in einen anderen Schnitt wird eine dort abweichende Zelle nicht als Quelle markiert.

Die Auswahl ist auf genau einen Report/Template/KPI-Sprung begrenzt. Neuer Report oder manuelle Filtereingabe verwirft sie. Peer-Neurendern erhält Fokus und Markierung; Skalierung und EUR-Konvertierung erhalten die Zuordnung zum Rohwert. Die Zelle erhält eine EN/DE-Beschreibung mit Kennzahl, angezeigtem Wert und Koordinate. Reduzierte Bewegung verwendet einen sofortigen Sprung.

## Validierung

- **1.471 vorhandene Tests erfolgreich**, keine übersprungen; gebaute Zweig-A-Artefakte vorhanden. [Testabschluss](test_suite.txt).
- **11 zusätzliche Browserfälle, 19 Quellsprünge**, keine JavaScript-Fehler. CET1, TREA und berechneter Headroom bei 1280×844 und 390×844, EN/DE, Hell/Dunkel, Klick/Enter/Touch, verzögerte Labels/Peer-Neurendern. Die zwei Dunkel-Fälle verwenden reduzierte Bewegung und prüfen die Sichtbarkeit unmittelbar nach dem Rendern.
- TREA bleibt bei voller/Milliardenskalierung und EUR-Schalter derselben Quellkoordinate zugeordnet. Ein echter SEK-Bericht bestätigt: Der EUR-Overview-Wert unterscheidet sich vom Originalbetrag; die Quellzelle bleibt vor und nach EUR-Umschaltung dieselbe, die Rohwerte bleiben unverändert.
- Fehlende Zelle, widersprüchlicher zweiter Wert an derselben Koordinate sowie zwei unterschiedliche Dimensionsschnitte werden in isolierten Browserfixtures auf Desktop und Mobil geprüft. Die falsche Zelle bleibt unmarkiert.
- Der vollständige Viewercheck ist erfolgreich. Auch die bestehende Quellnavigation (14 Fälle, 24 erfolgreiche Sprünge einschließlich Suche über zwei Templates und zwei verworfener alter Sprünge), Lokalisierung, Einheiten, Peer-Kontext und CSV bleiben abgesichert. Die zusätzliche Zellenprüfung ist in diesen CI-Check eingebunden. [Browserprotokoll](browser_validation.txt).
- Keine zusätzlichen Produktions-Requests. Koordinaten-/Fokusattribute werden nur an die markierten Zellen angehängt; alle übrigen Zellen bekommen keine zusätzlichen Datenattribute. Der Viewer wächst gegenüber `main` um **885 Bytes gzip** (Level 6).

Mobilprüfung in Chromium; kein physischer Safari-Test. Produktiv nach Merge und Pages-Deployment.
