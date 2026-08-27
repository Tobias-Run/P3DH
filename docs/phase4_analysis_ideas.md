# Phase 4 — Analyse-Ideen (Brainstorm, datengeerdet)

**Stand:** 2026-08-26 (Ursprung 2026-06-21 bei 8 Instituten; Datenrealität und
Bewertungen seither grundlegend aktualisiert — Historie in Git).

## Datenrealität (Basis für Machbarkeit)

| Dimension | Ist-Stand |
|---|---|
| Geladen | 553 Reports · 445 Institute · 30 Länder · 7 Module · 1,26 Mio. Facts |
| Gesamtbestand Hub | 4.278 Submissions · 489 Institute (`manifest_full.csv`) |
| Stichtage | 1 volle Welle (2025-12-31) + 20-%-Sample-Rest (06/09-2025, 03-2026) |
| Zeitreihen-fähig | nur Institute mit ≥2 Stichtagen; breite Trends erst nach weiteren Wellen |
| Framework | 4.1 und 4.2 gemischt; 4.2 bisher nur Q1-2026-Meldungen (22 Reports) |
| DPM-Labels | ✅ vollständig aufgelöst (`dpm_codebook.csv`); Filing-Indicators ✅ sauber |
| Einheiten | EUR-Normalisierung (EZB-Kurse) in Zweig B; decimals-Semantik beachtet |

**Die früheren Blocker (DPM-Labels, Filing-Indicator-Bug, N=8) sind Geschichte.**
Was die Reihenfolge heute bestimmt: erst *eine* volle Stichtags-Welle
(Querschnitt ja, Zeitreihe dünn) und der laufende 4.1→4.2-Wechsel.

---

## Geschäftsmodell-Abhängigkeit (Befund vom 22.06., gilt weiter)

Empirisch am N=8-Sample belegt, von der Skalierung auf 445 Institute nicht
entkräftet: Der Template-Fußabdruck folgt **Regulierungskategorie ×
Geschäftsmodell**. Kern (OV1, KM1, CC1/CC2) melden alle; Marktrisiko-, CCR-,
Verbriefungs- und IRB-Templates nur Kapitalmarkt-/IRB-Häuser; kleine Sparkassen
melden 4–9 Templates (Proportionalität, Art. 433a–c CRR). Spannweite im
damaligen Sample: 4 (Rietumu) bis 45 (DekaBank) Templates — Faktor >10.

**Konsequenzen (unverändert gültig):**
1. Peer-Vergleiche brauchen **Schichtung** nach Geschäftsmodell/Größenklasse —
   mit 445 Instituten und `entity_meta.csv` (Größe, Typ, G-SII) jetzt real möglich.
2. „Fehlt ≠ Null" braucht den dritten Zustand **„strukturell nicht anwendbar"**
   (Template fehlt, weil geschäftsmodellbedingt irrelevant — kein Versäumnis).

---

## ⚠️ Herabgestuft: Disclosure-/„Transparenz"-Profil (ehem. Idee A)

**Einwand des Nutzers (26.08., übernommen):** Banken legen offen, wozu sie nach
CRR Teil 8 verpflichtet sind — *welche* Templates, bestimmt die Institutskategorie
(Art. 433a–c) plus Anwendbarkeit (IRB-Zulassung, Handelsbuch …). Ein
„Transparenz-Score" auf dem Template-Fußabdruck misst daher im Wesentlichen die
**Regulierungskategorie, nicht Offenherzigkeit**.

Was bleibt davon:
- eine **Anwendbarkeits-/Kategorie-Karte** — nützlich als QA-Fundament und als
  Schichtungsgrundlage für Benchmarks, aber kein eigenständiges
  Erkenntnis-Deliverable;
- echter Ermessensspielraum sitzt eng begrenzt in **Art. 432 CRR**
  (Auslassung als „nicht wesentlich / geschäftsgeheim / vertraulich"): erkennbar
  höchstens als *Anomalie-Signal* — ein Institut meldet `false`, wo seine
  geschichtete Peer-Gruppe `true` meldet. Mit N=445 erstmals prüfbar, aber
  explorativ;
- echte Offenheits-Unterschiede (Boilerplate vs. Substanz) stecken in den
  narrativen PDFs → Idee G, nicht hier.

Deckt sich mit der Roadmap-Entscheidung vom 21.08. (Disclosure-Matrix nur
⚗️ Experiment, niedrige Prio).

## ✅ Erledigt: Framework 4.1→4.2 Struktur-Diff (ehem. Idee B)

Umgesetzt als **Phase 3b** → `docs/phase3_framework_bridge.md`,
`codebook/framework_bridge.csv` (Builder + Tests im Repo). Kernbefund:
Template-Ebene stabil (scheinbare Unterschiede waren Frequenz-Artefakte
Jahres- vs. Quartalsmeldung); Zell-Ebene 916 stabil / **19 auf neue dp-Codes
umgebunden** — ausgerechnet KM1-Leverage-Puffer, OV1-AIM, CVA, LR2-SFT.
Zeitreihen daher über `(template, row, col)` oder die Brücke joinen, nie naiv
über den dp-Code.

## ✅ Erledigt (Issue #9): Einheiten-QA über alle monetären Templates

Ausgangsbefund: Spalte a von `41.00` ist als **„Gross carrying amount (Mln EUR)"**
beschriftet, die Institute melden aber ganz überwiegend in **Währungseinheiten**.
Die Werte von Zeile 0010 streuen bimodal über `10^2` bis `10^12` — eine
Minderheit hat das Label wörtlich genommen, die Masse nicht (Raiffeisen-Holding
NÖ-Wien `9.520`, Groupe Crédit Agricole `440.552.425.122`; beides plausibel,
aber verschiedene Einheiten).

**Root Cause geklärt: kein Parser-Bug.** Das rohe XBRL-CSV trägt pro Fakt kein
scale/decimals-Attribut jenseits des global deklarierten `decimalsMonetary`
(Präzision, keine Skalierung — Sample-ZIP verifiziert `datapoint,factValue`,
sonst nichts). Die Diskrepanz ist echtes Filer-Verhalten, keine Ingestion-Lücke,
und institutsweise nicht sicher korrigierbar (ein kleiner Wert kann „echt klein"
oder „in Mio gemeint" sein — beides nicht unterscheidbar).

**Systematischer Check** (`scripts/check_unit_consistency.py`): zwei unabhängige
Prüfungen —
1. Gap-Scan über alle 5.039 monetären Zellen mit ≥6 Instituten: 91 mit einer
   Lücke ≥3 Größenordnungen. Größtenteils **falsch-positiv** durch legitime
   Long-Tail-Verteilungen (wenige Großbanken mit nennenswertem Exposure in einer
   Nischenkategorie, der Rest nahe null) — Kandidatenliste zur Sichtprüfung,
   nicht automatisch verwertbar.
2. Label-Cross-Check gegen `dpm_codebook.csv`: nur **`K_41.00`** und
   **`K_45.00.a`** (beide „Gross carrying amount (Mln EUR)") nennen im Codebook
   explizit eine Nicht-Basis-Einheit. `45.00.A` zeigt dieselbe Verdachtslage wie
   41.00 (Streuung `10^0`–`10^11`), aber keinen sauberen bimodalen Split — die
   beiden Prüfungen ergänzen sich, keine ersetzt die andere.

**Konsequenz, jetzt maschinenlesbar statt nur dokumentiert:** neue Spalte
`unit_ambiguous` in Zweig B (`build_zweig_b.py`), `True` für alle monetären
Zellen in 41.00/45.00.A (97.249 + 46.466 Fakten). Konsumenten filtern/caveaten
darauf, statt die Sperrliste in jedem Profil neu zu duplizieren. **Quotienten
bleiben sicher** — Zähler und Nenner stammen aus demselben Report und derselben
Einheit, die Einheit kürzt sich weg. Das ESG-Benchmark-Profil zeigt deshalb
bewusst nur Anteile (nachhaltig, Paris-ausgeschlossen, Stage 2, notleidend),
keine Beträge.

## C. Währungs- & Präzisions-QA (offen, klein)

30 Länder → viele Nicht-EUR-Währungen. Zweig B rechnet bereits EUR-normalisiert
(`fx_rate`, `fact_value_eur`); ein systematischer QA-Pass steht aus (Ausreißer
durch decimals-Fehlinterpretation, FX-Stichtagslogik). QA-Gate vor monetären
Querschnitts-Aussagen.

---

## Tier 2 — entblockt (DPM-Join steht, N=445)

### D. Kapital-/Solvenz-Benchmarking (KM1/OV1) — läuft
Im JSON-Viewer live (4 Benchmark-Profile, EUR-normiert, Sparklines). Nächster
Ausbau laut Roadmap 21.08.: Profile ausdehnen (NPL CR1/CQ3, ESG 41.00,
Kreditrisiko-Mix) + Perzentil-Bänder — je **geschichteter** Peer-Gruppe.

### E. Risiko-Komposition / Geschäftsmodell-Fingerprint
RWA-Mix (Kredit/Markt/Op) als Cluster-Merkmal — mit 445 Instituten methodisch
erstmals sinnvoll; OV1 liegt für 476 Reports vor.

### F. Zeitreihen
Erst nach der nächsten vollen Welle belastbar; über den 4.1→4.2-Wechsel **nur
via `framework_bridge.csv`** (die 19 umgebundenen Zellen treffen KM1 direkt).

### G. NLP auf qualitativen PDF-Narrativen
Weiter spekulativ: `*DISDOCS`-PDFs bewusst nicht ingestiert. Wäre der einzige
Ort, an dem sich die Frage messen ließe, die Idee A nicht beantworten kann —
wie offenherzig ein Institut jenseits der Pflicht kommuniziert.

---

## Empfohlene Reihenfolge (aktualisiert 26.08.)

1. **Benchmark-Substanz vertiefen** (Roadmap 21.08., Punkt 1+2): mehr Profile,
   Perzentil-Bänder — geschichtet nach Geschäftsmodell/Größe.
2. **C (FX/decimals-QA)** als Gate parallel dazu.
3. **Nächste Stichtags-Welle laden** → macht F (Zeitreihen) real und die
   4.2-Seite der Brücke dicker.
4. **E** (Fingerprint) danach; **G** (PDF-NLP) nur bei explizitem Bedarf.

## Querschnitts-Caveats (in jede Analyse)

- CON vs IND nicht mischen; Rechnungslegung/nationale Optionen als Caveat benennen.
- 4.1 vs 4.2 nur über `codebook/framework_bridge.csv` verbinden.
- „Fehlt" ≠ „Null" ≠ „strukturell nicht anwendbar" (drei Zustände auseinanderhalten).
- Peer-Aussagen nur innerhalb geschichteter Gruppen (Geschäftsmodell/Größe).
