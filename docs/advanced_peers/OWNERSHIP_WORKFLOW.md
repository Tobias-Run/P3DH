# Eigentümerrecherche mit begrenztem Kontext

Stand: 3. Oktober 2026. Die weitere Recherche ist **auf TREA-Priorisierung umgestellt**. Nach den Paketen 001–016 sind 207/475 Institute belegt, 268 bleiben offen. 212 der offenen Kennungen sind nach technischen Qualitätsfiltern per TREA priorisierbar; 56 benötigen gesonderte Größen-/Qualitätsprüfung. Das Clustering verwendet bereits TREA und wurde methodisch nicht umgestellt.

## Feste Standardgrenzen

| Grenze | Standard | Zweck |
|---|---:|---|
| Institute je Lauf | 5 | Kleine, abschließbare Recherchepakete |
| Seitenversuche je Institut | 4 | Höchstens 20 Quellabrufversuche im automatisierten Paket; Cachetreffer zählen mit. Redirects können zusätzliche HTTP-Anfragen auslösen |
| Gleichzeitige Collector-Worker | 2 | Begrenzte Quellenlast; das sind keine zusätzlichen KI-Agenten |
| Belegauszüge je Institut | 2 | Konzentrierte manuelle Prüfung |
| Zeichen je Belegauszug | 650 | Ganze Berichte bleiben außerhalb des Gesprächskontexts |
| Zeichen im gesamten Review-JSON | 12.000 | Technisch geprüfte Obergrenze für dieses Kontextpaket |

Das Zeichenlimit ist **kein exaktes Token- oder Kostenlimit**. Tokenisierung, sonstiger Gesprächskontext, Werkzeugaufrufe und Antworten zählen zusätzlich. Der Collector ruft kein Sprachmodell auf. PDF-/HTML-Auswertung, URLsuche im Cache und Ranking laufen lokal; nur ausgewählte Auszüge werden für die manuelle Prüfung gelesen. Für eine belastbare Kostenobergrenze eines späteren API-Recherchejobs wären zusätzlich ein gewähltes Modell, dessen Tokenizer sowie gemessene Ein-/Ausgabetokens mit einem Abbruchbudget erforderlich. Im aktuellen Chat kann dieses Skript den gesamten Sitzungsverbrauch nicht kontrollieren.

## Ablauf

1. **Warteschlange neu bauen.** Bereits klassifizierte Institute werden entfernt. TREA wird aus KM1, Zeile 0040, Spalte 0010 gelesen, je Kennung vom jüngsten technisch nutzbaren Stichtag; bei gleichem Datum CON bevorzugt. Keine TREA-Schätzung aus Namen oder Größenklasse. Mehrdeutige Beträge/Dimensionen/Einheiten, relevante Scale-Befunde und explizite Währungsprüffälle werden ausgeschlossen. Bank Millennium H1 2025 steht in der separaten Recherche-Sperrliste; die ursprünglichen Facts bleiben unverändert.
2. **Vorhandene Quellen zuerst durchsuchen.** Bereits akzeptierte Konzernträger, Belegpassagen, Websiteantworten und Geschäftsberichte wiederverwenden. Die Queue nennt mögliche Konzernträger und bereits geprüfte Eigentümerquellen als kurze Wiederverwendungshinweise. Die ältere Konzernbeziehung ist dabei noch kein aktuell geprüfter Bank-Kontrollnachweis. Ein Bank-spezifischer Kontrollnachweis bleibt erforderlich; die Trägerschaft wird nicht automatisch aus einem Parent-Namen abgeleitet.
3. **Bei Bedarf begrenzt abrufen.** Die ersten fünf offenen Fälle der Warteschlange verwenden höchstens vier Seitenversuche je Institut. Bekannte HTTP-403-Antworten werden nicht erneut abgerufen; temporäre Fehler respektieren den vorhandenen Cooldown/Retry-After. Websitekandidaten sind Recherchehinweise, keine verifizierten Eigentümerquellen.
4. **Kurze Belege manuell prüfen.** `review_bundle.json` enthält maximal zwei Auszüge je Fall samt URL/Hash. Ein Treffer, ein Prozentwert oder Börsennotierung ist keine automatische Klassifikation. Bankidentität, Stimmrechte, tatsächliche Kontrolle, Minderheitsanteile und Quellenstichtag müssen passen. Gespeicherte Volltexte/weitere Passagen können gezielt lokal durchsucht werden; nicht ganze Dokumente in den Chat ausgeben.
5. **Schwierige Fälle begrenzen.** Wenn das Paket keinen genügenden Nachweis liefert, Fall mit konkretem Folgeauftrag markieren. Im selben Paket nicht unbegrenzt zusätzliche Suchläufe starten. „Noch zu prüfen“ bedeutet nicht „öffentlich nicht vorhanden“. Eine gesonderte Tiefenrecherche ist ein eigener, sichtbar begrenzter Folgeauftrag.
6. **Ergebnisse dauerhaft speichern.** Akzeptierte Einordnungen kommen mit Quellen/Hash/Datum in `codebook/bank_classification.csv`, Paketentscheidungen in `ownership_batches/`, offene Fälle bleiben im vollständigen Rechercheledger. Nach Quellenprüfung Shards/Validierung und Warteschlange neu erzeugen. Atomare Einzelcheckpoint-Dateien verhindern, dass ein abgebrochener Schreibvorgang als fertiger Fall gilt.

## Befehle

Aus dem Repository, mit installierten Projektabhängigkeiten:

```bash
python scripts/build_ownership_research_queue.py
python scripts/research_bank_ownership.py \
  --discovery docs/advanced_peers/ownership_priority.json \
  --output interim/ownership_research \
  --max-banks 5 --max-pages 4 --max-context-chars 12000
```

Für einen ersten Lauf ganz ohne neue Abrufe ergänzen:

```bash
--cache-only --cache-dir /pfad/zum/vorhandenen/pages-cache
```

Cache-only liest auch bei alten temporären Fehlern ausschließlich vorhandene Dateien. Dieser Probe-Durchlauf blockiert den ersten späteren begrenzten Live-Durchlauf nicht. Schon abgeschlossene Live-Collector-Fälle werden beim nächsten Lauf übersprungen; die Einzelcheckpoint-Dateien bleiben erhalten. Bereits klassifizierte Kennungen werden zusätzlich beim Collectorstart aus dem aktuellen Register entfernt, auch wenn eine ältere Queue-Datei übergeben wird.

`--repeat` besucht gespeicherte Fälle ausdrücklich erneut; Cache- und 403-Schutz bleiben aktiv. Reguläre weitere Pakete brauchen dieses Flag nicht. `research.json` und `review_bundle.json` zeigen das zuletzt gesammelte Paket; die einzelnen `<LEI>.json`-Dateien enthalten weiterhin die früheren Fälle. Wenn das Zeichenbudget für einen Fall nicht reicht, wird er als `deferred_leis` ausgewiesen; der vollständige Checkpoint wird nicht gelöscht.

Die Warteschlange besitzt CSV, Collector-JSON und ein Manifest mit Quellhashes. Sie ist ein neu erzeugbarer Recherchestand, keine automatische Produktionspipeline. Nach neuen Facts oder akzeptierten Einordnungen muss sie neu gebaut werden. Eine Recherchepriorität ist noch kein Quellenbeleg.

## Erster Pilot

[Batch 001](ownership_batches/batch_001.json): fünf TREA-priorisierte Fälle, **null neue Netzwerkabrufe**. Bank of America Europe DAC wurde anhand ihres Eintrags im bereits archivierten SEC-Tochterverzeichnis und der bereits geprüften Aktionärsquelle des Konzernträgers explizit eingeordnet. Das belegt Konzernzugehörigkeit; ein 100-%-Anteilsbesitz wird daraus nicht behauptet. Die anderen vier Fälle (Bpifrance, Eurobank, RCI Banque und Caixa Geral de Depósitos) bleiben zur gezielten Quellenprüfung offen.

Das erste automatisierte Cache-Reviewpaket umfasste 947 Zeichen. Das ist ein tatsächlicher Zeichenmesswert dieses Pakets, kein gemessener Gesamttokenverbrauch. Die manuelle Wiederverwendung der archivierten SEC-/Aktionärsquellen wird separat dokumentiert; akzeptierte Quellenarchive unterliegen nicht dem Auszugslimit des Collector-Reviewpakets.

## Kontrolle

Tests prüfen TREA-Reihenfolge, Scope-/Datumswahl, Mengen-/Dimensionskonflikte, Sperrfälle, Skip bereits geprüfter Institute, Wiederaufnahme, reine Cache-Läufe ohne Netzwerkzugriff, harte Kontextgrenze ohne Verlust vollständiger Belege und atomare Checkpoints. Eigentümerbelege und bankbezogene Konzernquellen werden separat geprüft. Auszüge können durch das Zeichenlimit unvollständig sein: vor einer Klassifikation muss die entscheidende Passage im archivierten/öffentlichen Original vollständig gelesen werden.

## Zweites Paket: gezielte Quellenprüfung

[Batch 002](ownership_batches/batch_002.json) prüft die nächsten fünf nach TREA: Bpifrance, Eurobank, RCI Banque, Caixa Geral de Depósitos und Crédit Agricole Italia. **18 Quellenversuche / 17 neue Abrufe**, höchstens vier je Institut. Gezielt ausgewählte URLs und Cachequellen ersetzen einen breiten erneuten Crawl. Eurobank und CGD wurden mit direkten offiziellen Eigentümerbelegen ergänzt; drei Fälle bleiben offen. Ein temporärer 502, ein falscher 404-Link und 403-Sperren sind technische Ergebnisse, keine Aussagen zur öffentlichen Verfügbarkeit der Eigentümerdaten.

Das komprimierte Entscheidungs-JSON umfasst **4.423 Zeichen**; zusätzliche kurze Quellenprüfungen und Werkzeugausgaben sind darin nicht enthalten. Auch dieser Wert misst keine Gesamttokens. Das komplette versionierte Paket enthält außerdem Abrufprotokoll, Quellhashes und konkrete Nachprüfungen. Einzelcheckpoint-Dateien wurden im üblichen lokalen Ausgabeordner `interim/ownership_research/` gespeichert. Der nächste Lauf mit demselben Ausgabeordner überspringt diese bereits geprüften Fälle; die drei ungeklärten Banken bleiben in der Warteschlange und im Ledger und können gezielt wiederaufgenommen werden.

Bei Crédit Agricole Italia wurde eine nur `ENTITY_SUPPLIED_ONLY` belegte GLEIF-Beziehung ausdrücklich nicht als vollständig corroboriert akzeptiert. Bei RCI fehlt noch die geprüfte Eigentümerstruktur des exakten Renault-Konzernträgers. Für Bpifrance ist der nächste Schritt ein amtlicher Beteiligungsbericht des Staates bzw. der Caisse des Dépôts mit genauer Rechtsträgerzuordnung. Aktuelle Trägerschaftslabels bilden keine historische Eigentümer-Zeitreihe; Eurobanks verwendete Aktionärsseite nennt den 4. September 2026.

## Pakete 003–016: nächste 70 Fälle

Die [feste Auswahl und Einzelfallentscheidungen](NEXT70_OWNERSHIP.md) enthalten **20 akzeptierte Einordnungen und 50 konkrete Nachprüfungen**. Auswahl vor Klassifikationsänderungen eingefroren; die drei offenen Fälle aus Batch 002 wurden durch gespeicherte Checkpoints nicht erneut breit untersucht. 235 Quellenversuche / 171 neue Abrufe; höchstens vier Versuche pro Bank. Vier neue Dokumentketten verwenden bereits archivierte DNB/KBC-Berichte und das Citigroup-SEC-Tochterverzeichnis; dafür erfolgten keine weiteren HTTP-Aufrufe. Archivsuche und vorhandene Register-/ELF-Daten bleiben lokale Arbeit.

Das größte komprimierte Entscheidungs-JSON umfasst **4.543 Zeichen**. Zusätzlich wurden kurze Quellenauszüge manuell geprüft; das ist kein gemessener Gesamttokenverbrauch und kein Nachweis einer bestimmten Tokenersparnis. Alle 70 Checkpoints liegen im üblichen lokalen Ausgabeordner; der nächste reguläre Lauf überspringt sie, ihre noch offenen Fälle bleiben im Ledger und in der Queue. Versionierte Entscheidungen erlauben gezielte Wiederaufnahme.

**Verbesserungsbedarf der Quellensuche:** 56 Versuche lieferten HTTP 404, drei HTTP 410. Vermutete Blattseiten waren häufig falsch oder veraltet. Für die gezielte Fortsetzung zuerst die tatsächliche offizielle IR-/Corporate-Navigation, verlinkte aktuelle Geschäftsberichte oder amtliche Register verwenden; nicht weitere Varianten desselben vermuteten Pfads probieren. Leere/generische HTTP-200-Seiten gelten nicht als Nachweise. Die 50 Fälle sind ausdrücklich keine Behauptung, dass Eigentümerinformationen öffentlich fehlen.
