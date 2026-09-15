# Review der offenen Issues

Erhoben **2026-09-13** nach PR #87, nachgezogen **2026-09-15** nach den PRs
#89, #90 und #91. **27 offene Issues.**

Dieser Review ist eine **Momentaufnahme** und veraltet mit jedem Merge. Er steht
trotzdem im Repo, weil die Alternative — die Einschätzung nur im Issue-Verlauf —
sie über 27 Threads verteilt und damit unlesbar macht. Jede Zahl darin ist am
Bestand gemessen, nicht aus den Issue-Texten übernommen.

Die Befunde stehen zusätzlich als Kommentar an den jeweiligen Issues, damit
niemand dieses Dokument kennen muss, um den Stand seines Issues zu sehen:
#14, #31, #32, #34, #36, #41, #44, #45, #59, #83, #88.

## Was seit der Erhebung geliefert wurde

Der Review hat zu sechs Issues einen nächsten Schritt benannt. Alle sechs sind
inzwischen gebaut — und drei Issues sind damit ganz erledigt.

| Issue | Was hier als nächster Schritt stand | Stand |
|---|---|---|
| #83 | „`build_footprint.py` liest `scale_flags.csv` nicht — der billigste nächste Schritt im ganzen Backlog" | ✅ PR #90 |
| #34 | „Der Hebel mit der breitesten Wirkung … es fehlt die Ableitung als eigenes Artefakt" | ✅ PR #90, Punkt 1 von 2 |
| #43 | Punkt 4 — Zeitdimension, hing an #34 | ✅ PR #93 |
| #32 · #42 | „zwei Konzerngraphen, die nie gegeneinander geprüft wurden" | ✅ PR #90 |
| #45 | Punkt 3 — IRB-Risikogewichte je PD-Band | ✅ PR #89 |
| #41 | Machbarkeitsprüfung mit eigener Abbruchschwelle | ✅ PR #89 — **Issue geschlossen** |
| #88 | vom Review selbst gefunden | ✅ PR #89 + #92 — **Issue geschlossen** |
| #36 | hing an #34, siehe Abschnitt B | ✅ PR #91 — **Issue geschlossen** |

**Eine Lehre daraus, die den Review selbst betrifft.** Zwischen der Erhebung und
heute sank die Zahl der offenen Issues von 29 auf 27, während sieben
Arbeitspakete fertig wurden. Der Zähler misst diese Arbeit nicht, weil die
meisten Issues mehrere Punkte tragen und teilgeliefert offen bleiben. Wer den
Fortschritt am Zähler abliest, sieht Stillstand, wo keiner ist — und umgekehrt
wäre ein Issue, das nach dem ersten von vier Punkten geschlossen wird, eine
verlorene Anforderung. Die Spalte „Stand" oben ist das ehrlichere Mass.

## Zusammenfassung

| | Anzahl |
|---|---:|
| Teilergebnis geliefert, bewusst offen gelassen | 10 |
| nicht angefasst, mit heutigem Bestand rechenbar | 8 |
| nicht angefasst, braucht externe Quelle oder Netz | 4 |
| Betrieb / Wellen | 2 |
| sehr niedrige Priorität | 3 |

---

## A. Teilergebnis geliefert — was genau noch fehlt

Diese Issues haben ein Artefakt im Repo. Sie sind **nicht** erledigt, und der
Rest ist jeweils benannt.

### #83 — Skalenfehler *(bug)*

`processed/scale_flags.csv`: 54 Reports `skaliert`, 17 `verdacht`, 48 einzeln
skalierte Templates. Der Viewer markiert 100 Reports, 50 davon ohne jeden
Plausibilitätsbefund.

**Klasse C ist teilweise gedeckt — durch #45, nicht durch #83.** Nachgerechnet
markiert `rwa_density.skalenverdacht = true` neun Reports; fünf davon kennt auch
`scale_flags.csv`, die übrigen **vier sind exakt die Klasse-C-Fälle**: National
Bank of Greece, Banca Transilvania, AB Artea bankas, Banque Banorient France.

| Klasse | Detektor | Stand |
|---|---|---|
| A — ganzer Report | `scale_flags.csv`, Reportebene | ✅ |
| B — einzelnes Template | `scale_flags.csv`, Templateebene | ✅ |
| C — einzelne Zelle | `rwa_density.skalenverdacht` | nur für die LR-Zelle |

Die beiden Detektoren sind also **komplementär, nicht redundant**. Offen bleibt
eine *allgemeine* Erkennung einzelner skalierter Zellen — was existiert, ist
eine Prüfung für eine bestimmte Zelle, geschrieben für einen anderen Zweck.

**Der ursprüngliche Aufhänger ist erledigt** *(PR #90)*. `build_footprint.py`
liest `scale_flags.csv`; von 377 Zeilen tragen 31 den Vorbehalt `skala`, und
keine davon ist noch `reliable = true`.

**Dazu ein dritter Detektor, der keiner sein wollte** *(PR #91)*. Der
Zeitvergleich aus #36 ist richtungsblind und sieht damit, was `robust_z` per
Konstruktion nicht sieht. 8 der 21 Report-Paare mit Strukturbruch enthalten
einen Report, den `scale_flags.csv` unabhängig als `skaliert` führt — und in
der richtigen Richtung: bei der Deutschen Pfandbriefbank ist der frühere
Report der skalierte. Die übrigen 13 kennt #83 nicht (Sparebanken Norge
25,3 %, Groupe BPCE 18,2 %, DNB Bank 14,4 %).

| Klasse | Detektor | Stand |
|---|---|---|
| A — ganzer Report | `scale_flags.csv` · `time_break` (#36) | ✅ zwei unabhängige |
| B — einzelnes Template | `scale_flags.csv`, Templateebene | ✅ |
| C — einzelne Zelle | `rwa_density.skalenverdacht` · `time_jump` (#36) | teilweise |

Klasse C ist damit nicht mehr auf die LR-Zelle beschränkt — `time_jump` erkennt
eine einzelne skalierte Zelle überall, **sofern das Institut zwei Stichtage
hat** (207 von 474). Für die übrigen bleibt die allgemeine Erkennung offen.

### #43 — Ermessensausübung nach Art. 432

`processed/omission_profile.csv` und `omission_templates.csv`. Punkte 1–3 des
Issues erledigt.

**Punkt 4 (Zeitdimension) ist geliefert** *(PR #93)*:
`processed/omission_persistence.csv`, 3.339 beurteilbare (Institut,
Template)-Paare. Die Aussage, die erst der Zeitvergleich trägt:
**Nichtanwendbarkeit ist dauerhaft, Ermessen kann wechseln** — wer ein Template
einmal offenlegt, dem ist es anwendbar. 523 Paare wechseln, davon 94 individuell
zuschreibbar; der Rest teilt seine Lage mit bis zu 36 anderen Instituten und ist
damit Meldekalender, nicht Ermessen.

Dabei ist eine Grenze von #34 sichtbar geworden, die dort nicht stand: **das
Frequenzmodell schätzt an Instituten mit allen vier Stichtagen und wird auf
Institute mit zweien angewandt.** Wer nur 30.06. und 31.12. meldet, war an der
Schätzung nie beteiligt — und erzeugt dann die Lage `0-1-`, die 36-mal
gleichzeitig auftritt.

Und der Ländervergleich aus
Punkt 3 trägt nicht: die Mediane liegen in fast allen 24 Ländern bei 0,000, die
Spitze (Belgien, Rumänien) bei 0,042. Das ist Rauschen an der Nachkommastelle,
kein Aufsichtsraum-Effekt.

### #45 — RWA-Dichte · #42 — Negativmenge · #37 — EBA-Abgleich

Alle drei mit Artefakt (`rwa_density.csv`, `coverage_gap.csv`,
`eba_reconciliation.csv`) und in PR #85 dokumentiert. Offen ist jeweils die
Ausweitung, nicht der Kern. Zu #45 siehe zusätzlich die Klassenaufteilung
unter #83 — `skalenverdacht` deckt dort die Klasse C ab.

### #32 — Konzerngraph

`processed/lei_relations.csv`, **508 Institute**: 187 mit gemeldeter direkter
Mutter, 317 mit begründeter Ausnahme (`NO_KNOWN_PERSON` 164,
`NON_CONSOLIDATING` 111, `NATURAL_PERSONS` 25, `NO_LEI` 12, `NON_PUBLIC` 5),
4 ohne Meldung.

Offen sind die Punkte 3–5 (Aggregate, die den Graphen *benutzen*). Heute hat er
genau einen Konsumenten: `build_eba_reconciliation.py` schliesst über ihn 90
Institutszeilen aus, deren Mutter selbst meldet.

**Die beiden Konzerngraphen sind inzwischen gegeneinander geprüft** *(PR #90,
`processed/group_graph_check.csv`)*. `coverage_gap.csv` (#42) erkennt
Gruppenabdeckung über die **EZB-Hierarchie**, `lei_relations.csv` (#32) über
GLEIF. 97 Institute haben in beiden einen Kopf:

    67  identisch
    30  ssm_schnitt   GLEIF-Kopf ausserhalb der EZB-Liste
     0  konflikt

**Kein Widerspruch** — und die 30 Abweichungen sind kein Fehler, sondern die
Perimetergrenze: bei 27 davon ist der EZB-Kopf das Institut selbst, weil der
Konzern über den SSM hinausreicht (BofA Securities Europe → Bank of America,
HSBC Continental Europe → HSBC Holdings). Keiner der Graphen ersetzt den
anderen; für die Länderaggregate in #37 ist der EZB-Kopf der richtige.

### #38 — DISDOCS-Korpus

`interim/disdocs_manifest.csv` und `disdocs_probe.csv`. Schritt 3 blockiert an
der Sprachbarriere; der LLM-Workflow ist im Issue beschrieben, nicht gebaut.

### #49 — Visuelle Kodierung

Größenbalken gebaut. **Offen: die Verteilungsspalte je Zeile.** Heute steht die
Verteilung als Karte über der Liste (#48) und die Position als Perzentilmarke in
der Zelle — zusammen decken sie die Frage, aber nicht in der skizzierten Form.

### #50 — Teilbarer Zustand und Export

Teilbarkeit vollständig (Filter, Profil, Sortierung, Auswahl), Export gebaut.
**Offen: Spaltenauswahl.** Gespeicherte Sichten halte ich für erledigt-durch-
Umgehung: ein teilbarer Link *ist* eine gespeicherte Sicht, und zwar an einem
Ort, den der Browser ohnehin verwaltet.

### #14 — BIP als Kontextspalte

`codebook/country_gdp.csv`, 212 Länder, 99,68 % des Exposures, in
`datensatz.md` mit der Regressor-Warnung dokumentiert.

**Die Spalte wird nirgends benutzt** — ausser vom Abrufskript und der Doku liest
sie niemand. Der Zweck aus dem Titel, „Kontextspalte", ist damit nicht
eingelöst: ein Exposure von 5 Mrd EUR relativiert sich am maltesischen BIP
anders als am deutschen, und genau diese Relativierung sieht heute niemand.

---

## B. Nicht angefasst — mit dem heutigen Bestand rechenbar

Nach Aufwand-zu-Ertrag geordnet, mit dem Grund.

### ~~#34 — Frequenzmodell je Template~~ → Punkt 1 geliefert *(PR #90)*

`processed/disclosure_frequency.csv`, 184 Koordinaten. Gemessen statt aus der
CRR abgeschrieben: über 4.407 (Institut, Template)-Paare mit allen vier
Stichtagen fallen **96,5 % in genau vier Muster** (`1010` halbjährlich 36,2 % ·
`0000` nie 33,6 % · `0010` jährlich 15,6 % · `1111` vierteljährlich 11,1 %).

Gemessen wird das Muster eines EINZELNEN Instituts über die vier Stichtage,
nicht die Quote je Population — der naheliegende Weg hätte ein Drittel der
Fälle im mehrdeutigen Mittelfeld gelassen (32 % zwischen 20 und 80 %).

**Offen bleibt Punkt 2, und das ist laut Issue „das eigentliche Produkt":** die
*Abweichung* vom Muster als Signal — ein Institut, das ein Template einstellt,
das seine Frequenzklasse weiter meldet. Das Modell ist die Vorarbeit, nicht der
Befund.

### ~~#36 — Intra-Instituts-Konsistenz über die Zeit~~ → **erledigt** *(PR #91)*

Vierte Regelfamilie in `check_plausibility.py`: 4.870 `time_jump` und 42
`time_break` neben unverändert 5.816 Zellausreissern und 214
Korridorverletzungen — in EINEM Profil, wie das Issue verlangt.

Drei Annahmen des Issues trugen nicht, und alle drei sind im Issue-Kommentar
belegt: der vorgeschlagene Schlüssel (Template, Zeile, Spalte) ist keine Zelle
(268 Koordinaten tragen mehrere Datenpunkte, was 16.048 „Sprünge" über null
Tage erzeugt); die Framework-Brücke sperrt nicht, sondern übersetzt (ein
dp-Join verliert die umgebundenen Zeitreihen still, 1.055 Paare entstehen erst
durch die Brücke); und die Frequenz trägt einen Vorbehalt, keinen Filter —
Jahr gegen Quartal ist Faktor 4, also 0,6 Grössenordnungen, weit unter der
Schwelle von 3.

**#34 war also nicht die Voraussetzung, für die dieser Review sie hielt.** Die
Einschätzung „braucht #34 vorher" war überzogen: sie stimmt für die
*Interpretation* eines kleinen Sprungs, nicht für die Erkennung eines grossen.

### #44 — Wirkt die Proportionalität?

**Weitgehend beantwortet, ohne dass es jemand aufgeschrieben hätte.** Aus den
#43-Daten, Offenlegungsumfang (offengelegt / deklariert) je CRR-Klasse:

| Klasse | n | Median |
|---|---:|---:|
| Large highest EEA | 394 | 0,383 |
| Large subsidiaries | 219 | 0,316 |
| Other highest EEA | 266 | 0,203 |

Monoton in der erwarteten Richtung. Was fehlt, ist die Frage *hinter* der Zahl:
folgt der Umfang der Klasse, oder folgen beide der Größe? Das ist eine
Auswertung, keine neue Datenbeschaffung.

### #31 — Korrekturverhalten

`interim/edap_recon/manifest_full.csv`, 4.278 Einreichungen, ist im Repo.
Gemessen **472 Korrekturen**; ein Report wurde zehnmal eingereicht
(Bulgarien, CODIS, 2025-06-30, alle zehn Fassungen innerhalb von zwei Tagen).
Übrig bleiben 3.806 eigenständige Meldungen.

Diese Zahl stammt jetzt aus `scripts/submissions.py` (#88) und stimmt damit
exakt mit `docs/analysen_nach_vollload.md` überein. Die 466 in einer früheren
Fassung dieses Dokuments waren ein vierter Messfehler derselben Art: ein
URL-Präfix als Ersatzschlüssel, der sechs Korrekturen übersah.

⚠️ **Die Zahl hängt vollständig an der Definition von „dieselbe Meldung".** Drei
plausible Schlüssel geben 472, 2.539 und 3.353 Korrekturen — Faktor 7. Richtig
ist nur der Schlüssel *mit* dem Modultyp aus dem Dateinamen: die Spalte `module`
trägt nur den PILLAR3-Code (`020000`), und unter einem Code liegen CODIS, ESGDIS
und FINDIS als eigenständige Meldungen. Wer sie zusammenwirft, zählt
verschiedene Module als Korrekturen voneinander. Eine Auswertung zu #31 muss
diese Definition **nennen**, sonst ist ihre Kernzahl beliebig.

### #19 — Länder-Aggregate · #16 — Kreditverschlechterungs-Kette · #15 — Zinssensitivität

Datengrundlage vollständig vorhanden (`open_axis_country` auf 264.555 Fakten
über 250 Länder; `82.00.*`/`83.01.*`; `68.00`). Reine Auswertungen. #19
überschneidet sich stark mit `footprint.csv`.

### #59 — Ländercode-Verwechslungen

Bisher ohne jede Codezeile im Repo. **Der Review hat nebenbei einen Beleg
geliefert**, dass die Fehlerklasse real ist — allerdings nicht in den Werten,
sondern eine Ebene darüber: zwei Institute haben ihre Meldung zuerst unter
falschem Ländercode eingereicht und dann korrigiert.

```
549300O2UN9JLME31F08.IND_FR_..._2025-12-31   (UniCredit Banka Slovenija, SI)
21380033CFFM2V1ZCK65.CON_FR_..._2025-12-31   (Sparkasse Malta, MT)
```

Der Einreichungskatalog ist damit eine zweite, unabhängige Quelle für dieses
Issue.

### #27 — Ähnliche Institute vorschlagen

Viewer-Feature. Die Peer-Gruppen-Logik existiert (`peerKeyOf`,
`PCT_MIN_GROUP`), die Ähnlichkeitsmetrik nicht.

---

## C. Nicht angefasst — braucht externe Quelle

**#39** (Ereignisstudie, Kursdaten), **#40** (Wikidata), **#11** und **#13**
(Clustering — rechenbar, aber inhaltlich an #35 gekoppelt), **#35** (bipartiter
Graph).

Zu #11/#13/#35: kein Skript im Repo. Sie hängen an derselben Matrix
(Bank × Land aus `footprint.csv`) und wären als *ein* Arbeitsschritt billiger als
als drei.

### ~~#41 — OpenStreetMap~~ → **geschlossen, Abbruchempfehlung** *(PR #89)*

Das Issue nennt seine eigene Abbruchbedingung: „Eine Trefferquote unter ~50 %
ist ein legitimer Abbruchgrund." `scripts/probe_osm_branches.py` hat sie
gemessen — **48,9 % über alle Institute (23 von 47)**. Die Schwelle ist
erreicht, die Frage beantwortet, es ist nichts mehr zu bauen.

Zwei Befunde aus der Messung, die den Wert der Vorabprüfung belegen:

- Der naive Namensabgleich ordnete **36 Filialen der `Banco de Portugal`**
  (Zentralbank) einem Investmenthaus namens `Banco de Investimento Global` zu.
  Die Korrektur — generische Wörter streichen statt eine Längenschwelle — hat
  die Trefferquote von 55,8 % auf 44,2 % **gesenkt**. Ohne sie hätte die
  Analyse die Abbruchschwelle scheinbar überschritten.
- Die Verbundstrukturen (Sparkassen, Raiffeisen, Crédit Agricole), die das
  Issue als Risiko benennt, sind genau die Fälle, die nicht zuzuordnen sind —
  eine Marke über rechtlich eigenständige Institute hinweg.

Eine Wiederaufnahme bräuchte eine LEI-gestützte Verknüpfung, keine
Namensheuristik. Die Idee ist damit nicht widerlegt, ihr Weg ist es.

---

## D. Betrieb

### #7 — Nächste Stichtags-Welle

Im Bestand: 2025-06-30 · 09-30 · 10-31 · 12-31 · 2026-03-31. Die Frage ist
nicht, ob es geht, sondern wann die nächste Welle vorliegt.

### #8 — Wöchentlichen Cron scharf schalten

`pipeline.yml` Zeile 29/30, auskommentiert. Bewusst: ein Cron, der auf eine
unfertige Kette losgeht, produziert Commits, die niemand liest.

---

## E. Sehr niedrige Priorität

### #70 — Mehrdeutige Brückenzellen

Nachgemessen und **bestätigt**: von 5.277 Brückenzeilen sind 123 `ambiguous`,
und alle 123 liegen in `74.00` (LIQ2). Die Aussage des Issues stimmt unverändert.

### #28 — Reports ohne platzierbare Zelle *(bug)*

Nachgemessen, und der Befund ist **kleiner als der Titel vermuten lässt**:

| | |
|---|---:|
| Parse-Manifest | 885 Reports |
| mit Filing-Indicators | 883 |
| mit platzierten Fakten (Parquet) | 882 |
| im Viewer-Index | 882 |

Genau **ein** Report deklariert und liefert nichts Platzierbares
(`rs:969500O971S0I6U24G84.CON`, 2025-12-31); zwei weitere stehen im
Parse-Manifest ohne Filing-Indicators. Der Viewer verliert gegenüber dem Parquet
**nichts** — die Lücke sitzt davor.

---

## Was der Review selbst gefunden hat — #88

Ein Fund, der in keinem Issue stand: der Standard-Manifest von
`download_raw_reports.py` und `xbrl_csv_parser.py` ist `manifest_latest.csv` —
erzeugt von `resolve_latest_submissions.py`, dessen Schlüssel den Modultyp nicht
enthält. Wer die Skripte so aufruft, wie `docs/phase1_ingestion.md` es zeigt,
bekommt **1.746 statt 2.829** Einreichungen; FINDIS fällt von 617 auf 127,
ESGDIS von 289 auf 53.

Die Pipeline ist nicht betroffen, sie übergibt `manifest_parse.csv` explizit —
und `build_parse_manifest.py` beschreibt die Falle in seinem Docstring sogar
wörtlich. Es ist also **dieselbe Regel, zweimal implementiert, einmal richtig**.
Genau diese Klasse hat das Projekt schon mehrfach getroffen.

**Erledigt und geschlossen** *(PR #89 und #92)*. Die Regel steht jetzt einmal, in
`scripts/submissions.py`; beide Konsumenten defaulten auf `manifest_parse.csv`.

Die zweite Oberfläche brauchte einen eigenen Schritt und war die grössere: das
Issue nennt `docs/phase1_ingestion.md` wörtlich als die Stelle, an der Leser in
die Falle geführt werden — und dort stand die Anweisung, `manifest_latest.csv` zu
konsumieren, noch zwei PRs länger als der Code, den sie beschrieb. Die Doku
nennt jetzt `build_parse_manifest.py`, führt die 38 % als ausgewiesene Warnung
und nennt den produktiven Schlüssel. Ein Test in `tests/test_submissions.py`
hält fest, dass die alte Anweisung nicht zurückkommt.

Dass der Code repariert war und die Anleitung nicht, ist dieselbe Trennung wie
beim Fund selbst: **eine Regel, zwei Orte, einer davon veraltet.** Eine
Korrektur ist erst fertig, wenn auch die Stelle stimmt, die Leute tatsächlich
lesen.

## Zwei Irrwege dieses Reviews, damit sie nicht wiederkommen

Beide Male sah eine gemessene Zahl nach einem Befund aus und war keiner:

**„2.539 Korrekturen".** Der erste Schlüssel für #31 verschmolz CODIS, ESGDIS
und FINDIS desselben Instituts zu Korrekturen voneinander — weil die Spalte
`module` eben nicht der Modultyp ist. Die Doku mit ihren 472 hatte recht, die
Messung nicht.

**„4 Einreichungen fehlen im Parse-Manifest".** Sie fehlen nicht; mein Schlüssel
hatte `country` enthalten und damit die Korrektur eines falschen Ländercodes als
zweiten Report gezählt. Der produktive Schlüssel lässt `country` zu Recht weg.

**„248 gegen 54 — zwei Skalendetektoren widersprechen sich".** Sie widersprechen
sich nicht. `rwa_density.skalenverdacht` ist **dreiwertig**: `true` (9), `false`
(537), `unbekannt` (239). Ich hatte „nicht false" gefiltert und damit 239-mal
„nicht prüfbar" als Verdacht gezählt — ausgerechnet den Fehler, gegen den die
Dreiwertigkeit gebaut wurde. Richtig gerechnet ergänzen sich beide Dateien.

Dreimal derselbe Fehlertyp: der **Schlüssel bzw. Filter**, mit dem gemessen
wurde, war falsch — nicht das, was gemessen wurde. Und jedes Mal sah die Zahl
nach einem Befund aus. Wer hier weitermisst, prüfe zuerst, ob eine Spalte mehr
als zwei Zustände kennt und ob ein Gruppenschlüssel wirklich das identifiziert,
was er zu identifizieren vorgibt.
