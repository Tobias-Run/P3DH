# Umsetzung der Performance- und UX-Issues #115–#119

Die Issues werden auf `perf/github-pages-review` nacheinander umgesetzt und je
Schritt separat geprüft. Ausgangscode: `902d0add0d117473791d129bc2d9180e9761e7f4`.
Die ursprüngliche Untersuchung vom 30.09.2026 bleibt in
[performance_review.md](performance_review.md) als historische Referenz erhalten.
Die hier folgenden Ergebnisse betreffen die Weiterentwicklung dieses Kandidaten.

## Messbedingungen und Grenzen

Die lokale Messung verwendet den unveränderlichen Datenstand
`f8adc69c5e8b623b289211cf4bb2f463916d23bf`. Desktop und gedrosseltes Chromium
(390 × 844, CPU 4×, 4 Mbit/s, 60 ms) sind Laborbedingungen. Ein physisches
Smartphone und ein echter Screenreader stehen in dieser Umgebung nicht zur
Verfügung. Tastatur-, Touch-Ereignisse und zugängliche Zustände werden im Browser
geprüft; sie ersetzen diese manuellen Abnahmen nicht. Es wird kein Feld-INP
behauptet. Die Änderungen werden als PR zur Prüfung bereitgestellt.

## #115 – CPU-Optimierungen

Formatter-Cache, Zeitreihenindex und Midrank-Berechnung werden gemeinsam
übernommen. Die unbewiesene Änderung von `no-store` auf `no-cache` wird nicht
übernommen. Die Label-Ladestrategie bleibt bis #116 auf dem Ausgangsverhalten.

Der Äquivalenztest vergleicht acht Profile samt CSV, 883 Berichtszuordnungen,
Zahlenformate beider Sprachen, 1.001 synthetische Perzentilfälle und die vollständigen
Template-HTML-Ausgaben dreier großer Berichte. CSV-Zeitstempel und lokale URL
werden normalisiert. Ergebnisse: `performance/results/issue115_verification.json`.


## #116 – Berichtsprefetch und Fehlerbehandlung

Die erste Berichtsdarstellung startet die Labels, bevor sie optionale Peer-Daten
anfordert. Die Benchmark-Ansicht fordert weiterhin keine Labels an. Alle
Lesestellen warten auf erfolgreiche Beschriftungen. Ein sichtbarer Retry-Knopf
ermöglicht einen neuen Abruf nach Fehlern; gleichzeitige Leser teilen den Request.
Späte Report- und Label-Antworten dürfen eine andere Ansicht nicht überschreiben.

`performance/test_ux.py` prüft Touch-Öffnung, Request-Zusammenfassung,
Abruffehler/Wiederholen und Navigation während eines verzögerten Report-Abrufs.
`performance/measure_labels.py` misst die erste Tabellenöffnung sofort nach der
Übersicht sowie nach 1,5 Sekunden Lesezeit, jeweils fünfmal auf Desktop/Mobil.
Diese Definition ist strenger als die frühere Öffnung nach Netzwerkberuhigung.


Die fünf Wiederholungen der strengeren Öffnungsmessung ergeben mobil:
Ausgangsstand sofort 4.752 ms / nach 1,5 s Lesen 3.294 ms; gewähltes Prefetch nach
Übersicht sofort 2.434 ms / nach Lesen 580 ms. Die frühere Review-Zahl 864 ms
stammt dagegen aus einer Öffnung nach Netzwerkberuhigung und ist nicht direkt
vergleichbar. Ein zusätzlich getesteter früher Abruf bringt sofort 2.219 ms,
verzögert die Übersicht aber von 1.822 auf 2.177 ms. Deshalb bleibt die Variante
nach der ersten Übersicht. Rohdaten: `issue116_baseline_expansion.json`,
`issue116_late_prefetch.json`, `issue116_early_prefetch.json`.
Das Ideal unter einer Sekunde unmittelbar nach der ersten Übersicht ist damit
noch nicht erreicht; nach kurzer Lesezeit liegt der Median darunter.

## #117 – Begrenzte Tabellenansicht mit vollständigem Datenbestand

Wiederverwendete Zeilen allein reichen nicht: Die Darstellung aller 814 Zeilen
bleibt mobil teuer. Deshalb zeigt der Benchmark 100 Zeilen je Seite. Sortierung,
Filter, Perzentile, Balkenbasis und CSV verwenden weiterhin sämtliche passenden
Datensätze. Die Oberfläche nennt den sichtbaren Bereich und erklärt, dass die
Browsersuche nur die aktuelle Seite durchsucht. Die Anwendungssuche umfasst alle
Berichte. Zeilen und Bedienelemente werden wiederverwendet, Fokus bleibt erhalten;
der DOM-Cache hält höchstens eine Seite.

Der Browser prüft gecachte gegen vollständig neu erzeugte Tabellen für alle acht
Profile, die vollständige Reihenfolge über alle Seiten, CSV über alle Treffer und
mehrmalige Sortierung ohne doppelte Eventhandler. Messung nach beruhigtem Laden,
je fünf Aktionen: mobil Sortieren Median 317 ms, Filtern 477 ms. Das sind
synthetische Aktionslatenzen, kein Feld-INP. Der erste reine DOM-Wiederverwendungs-
Versuch bleibt als `issue117_full_dom_actions.json` dokumentiert.
