# Review der offenen Issues

Stand **2026-09-13**, nach dem Merge von PR #87. 29 offene Issues.

Dieser Review ist eine **Momentaufnahme** und veraltet mit jedem Merge. Er steht
trotzdem im Repo, weil die Alternative — die Einschätzung nur im Issue-Verlauf —
sie über 29 Threads verteilt und damit unlesbar macht. Jede Zahl darin ist am
Bestand gemessen, nicht aus den Issue-Texten übernommen.

## Zusammenfassung

| | Anzahl |
|---|---:|
| Teilergebnis geliefert, bewusst offen gelassen | 10 |
| nicht angefasst, mit heutigem Bestand rechenbar | 9 |
| nicht angefasst, braucht externe Quelle oder Netz | 5 |
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

**Offen: Klasse C — einzelne Zellen** (National Bank of Greece). Sie gehört zur
Zellprüfung und liegt dort auf derselben ungeprüften unteren Flanke, die den
Report-Detektor überhaupt nötig gemacht hat. Der ursprüngliche Aufhänger —
22 Zeilen in `footprint.csv` mit `reliable = true` — ist damit **noch nicht**
geschlossen: `build_footprint.py` liest `scale_flags.csv` nicht.

### #43 — Ermessensausübung nach Art. 432

`processed/omission_profile.csv` und `omission_templates.csv`. Punkte 1–3 des
Issues erledigt.

**Offen: Punkt 4** (Zeitdimension, hängt an #34). Und der Ländervergleich aus
Punkt 3 trägt nicht: die Mediane liegen in fast allen 24 Ländern bei 0,000, die
Spitze (Belgien, Rumänien) bei 0,042. Das ist Rauschen an der Nachkommastelle,
kein Aufsichtsraum-Effekt.

### #45 — RWA-Dichte · #42 — Negativmenge · #37 — EBA-Abgleich

Alle drei mit Artefakt (`rwa_density.csv`, `coverage_gap.csv`,
`eba_reconciliation.csv`) und in PR #85 dokumentiert. Offen ist jeweils die
Ausweitung, nicht der Kern.

### #32 — Konzerngraph

`processed/lei_relations.csv`, 508 Institute. Offen sind die Punkte 3–5 des
Issues (Aggregate, die den Graphen *benutzen*).

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

`codebook/country_gdp.csv`, 212 Länder, in `datensatz.md` dokumentiert.
Absichtlich offen gelassen, weil die Nutzung im Viewer fehlt.

---

## B. Nicht angefasst — mit dem heutigen Bestand rechenbar

Nach Aufwand-zu-Ertrag geordnet, mit dem Grund.

### #34 — Frequenzmodell je Template ⭐

**Der Hebel mit der breitesten Wirkung.** Bei #43 ist die Frequenz je
(Klasse, Stichtag, Template) beiläufig mitgemessen worden, und sie ist scharf:

| Template | 06-30 | 09-30 | 12-31 | 03-31 | Lesart |
|---|---:|---:|---:|---:|---|
| `61.00` KM1 | 96,5 % | 94,9 % | 95,0 % | 95,3 % | vierteljährlich |
| `74.00` LIQ2 | 62,8 % | 2,5 % | 62,9 % | 2,8 % | halbjährlich |
| `19.03` OR3 | 3,0 % | 1,7 % | 53,9 % | 1,9 % | jährlich |

Damit ist das Modell fast fertig — es fehlt die Ableitung als eigenes Artefakt.
Es entsperrt #43 Punkt 4 und macht #36 erst sauber interpretierbar.

### #36 — Intra-Instituts-Konsistenz über die Zeit

209 Institute mit ≥ 2 Stichtagen. Der stärkere Plausibilitätstest, weil er
Institutsgröße und Geschäftsmodell konstant hält, statt sie herausrechnen zu
müssen. **Braucht #34 vorher**: ohne Frequenzmodell ist jeder Sprung
mehrdeutig — ein Template, das halbjährlich gemeldet wird, „springt" zwischen
den Quartalen aus reiner Meldelogik.

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
Gemessen **466 Korrekturen bei 160 Instituten**; ein Report wurde zehnmal
eingereicht (Bulgarien, CODIS, 2025-06-30, alle zehn Fassungen innerhalb von
zwei Tagen).

⚠️ **Die Zahl hängt vollständig an der Definition von „dieselbe Meldung".** Drei
plausible Schlüssel geben 466, 2.539 und 3.353 Korrekturen — Faktor 7. Richtig
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

**#39** (Ereignisstudie, Kursdaten), **#40** (Wikidata), **#41** (OpenStreetMap),
**#11** und **#13** (Clustering — rechenbar, aber inhaltlich an #35 gekoppelt),
**#35** (bipartiter Graph).

Zu #11/#13/#35: kein Skript im Repo. Sie hängen an derselben Matrix
(Bank × Land aus `footprint.csv`) und wären als *ein* Arbeitsschritt billiger als
als drei.

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

Details und Vorschlag in **#88**.

## Zwei Irrwege dieses Reviews, damit sie nicht wiederkommen

Beide Male sah eine gemessene Zahl nach einem Befund aus und war keiner:

**„2.539 Korrekturen".** Der erste Schlüssel für #31 verschmolz CODIS, ESGDIS
und FINDIS desselben Instituts zu Korrekturen voneinander — weil die Spalte
`module` eben nicht der Modultyp ist. Die Doku mit ihren 472 hatte recht, die
Messung nicht.

**„4 Einreichungen fehlen im Parse-Manifest".** Sie fehlen nicht; mein Schlüssel
hatte `country` enthalten und damit die Korrektur eines falschen Ländercodes als
zweiten Report gezählt. Der produktive Schlüssel lässt `country` zu Recht weg.

In beiden Fällen lag der Fehler im Schlüssel, mit dem gemessen wurde — nicht in
dem, was gemessen wurde.
