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
