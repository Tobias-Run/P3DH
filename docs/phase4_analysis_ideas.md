# Phase 4 — Analyse-Ideen (Brainstorm, datengeerdet)

**Stand:** 2026-06-21. Geerdet an der tatsächlichen Datenabdeckung (nicht an den
generischen Phase-4-Vorschlägen der Instructions).

## Datenrealität (Basis für Machbarkeit)

| Dimension | Ist-Stand |
|---|---|
| Institute | 8 (LEIs), 16 aktuelle Submissions |
| Stichtage | 4 (2025-06-30, -09-30, -12-31, 2026-03-31) |
| Zeitreihen-fähig | 4 Institute mit ≥2 Stichtagen (1 davon mit allen 4) |
| Länder | DE, SE, AT, MT, EE, DK, LV |
| Konsolidierung | 11 CON / 5 IND (→ nicht naiv mischbar) |
| Währungen | EUR, SEK, DKK (→ EUR-Normalisierung ist real nötig, nicht theoretisch) |
| decimalsMonetary | -6, -3 und 2 gemischt (→ Präzisions-Semantik real nötig) |
| Framework | 4.1 (94 %) **und** 4.2 (6 %) gemischt (→ Brücke jetzt schon relevant) |
| Templates | 88 verschiedene über den Datensatz |

**Zwei harte Einschränkungen, die die Reihenfolge bestimmen:**
1. **DPM-Labels fehlen** — alle Datapoints sind `[TODO]`. Jede Analyse, die die
   *Bedeutung* einzelner Datapoints braucht (CET1, RWA, GAR …), ist blockiert,
   bis der DPM-Join steht.
2. **Filing-Indicators defekt** — `template_reported` ist derzeit immer `False`
   (BOM- + Key-Bug, siehe BACKLOG). „Fehlt ≠ Null" ist erst nach Fix vertrauenswürdig.
3. **Kleine Stichprobe — und geschäftsmodell-fragmentiert** — 8 Institute tragen
   kein robustes Peer-Benchmarking / Clustering. Verschärfend: die 8 verteilen sich
   auf ~6 sehr unterschiedliche Geschäftsmodelle (siehe Abschnitt „Geschäftsmodell-
   Abhängigkeit" unten), d. h. die *effektive* Peer-Gruppe ist eher 1–2 als 8.
   Querschnitt-Analysen sind vorerst „Methode bauen, Insight nach Skalierung der
   Ingestion".

---

## Geschäftsmodell-Abhängigkeit (Prüfung zu Einschränkung 3)

**Frage:** Trägt die Stichprobe von 8 Instituten ein Querschnitts-Benchmarking,
wenn man die Geschäftsmodelle berücksichtigt? **Antwort: nein — eher weniger als
die reine Zahl 8 suggeriert, aber die Heterogenität ist für die *Struktur*-Analyse
(Idee A) ein Gewinn, kein Verlust.**

### Die 8 Institute nach Geschäftsmodell-Archetyp

| Institut | Land | Kons. | Archetyp | gemeldete Templates |
|---|---|---|---|---|
| DEKABANK | DE | CON | Sparkassen-Zentralinstitut / Kapitalmarkt & Asset Mgmt | **45** |
| Aktiebolaget Svensk Exportkredit | SE | IND | Exportkreditagentur (Spezial-/Förderkredit) | 32 |
| NOBA BANK GROUP | SE | CON | Consumer-Finance / Nischenbank | 28 |
| HYPO TIROL BANK | AT | CON | Regionale Universalbank | 26 |
| AS INBANK | EE | CON | Digitale Consumer-Finance-Bank | 26 |
| SPARKASSE (HOLDINGS) MALTA | MT | CON | Kleine Sparkasse (Holding) | 9 |
| RØNDE SPAREKASSE | DK | IND | Sehr kleine lokale Sparkasse | 7 |
| RIETUMU BANKA | LV | CON | Commercial / Private Bank | **4** |

→ ~6 Archetypen auf 8 Institute. Spannweite der gemeldeten Templates: **4 bis 45**
(Faktor >10). Das sind keine 8 vergleichbaren Banken, sondern ein Spektrum vom
winzigen Einlageninstitut bis zum vollen Kapitalmarkthaus.

### Empirischer Beleg: der Template-Fußabdruck folgt dem Geschäftsmodell

Aus `processed/filing_indicators.csv` (reported=true), nicht aus Annahmen:

- **Universeller Kern (alle Archetypen melden):** `60 OV1` (Risikoexposure-Übersicht),
  `61 KM1` (Key Metrics), `66.01/66.02 CC1/CC2` (Eigenmittel-Zusammensetzung). Das
  ist das Pflicht-Rückgrat, das jede Bank einreicht.
- **Nur DekaBank, NICHT bei den kleinen Sparkassen (Rønde/Rietumu/Malta):**
  Marktrisiko (`10–13 MR1/MR2/MR3`), Kontrahentenrisiko (`02–08 CCR1–8`),
  Verbriefung (`09 SEC1/4`), IRB-Kreditrisiko (`26–29 CR6–10`), operationelles
  Risiko im Detail (`19 OR1–3`), LCR/NSFR (`73/74 LIQ1/2`), Prudent Valuation
  (`65 PV1`), Krypto-Assets (`01 CAE1`).

Diese Templates fehlen bei den Sparkassen **strukturell** — kein Handelsbuch, keine
IRB-Modelle, keine Verbriefung. Das ist Geschäftsmodell, nicht Intransparenz.

### Konsequenzen für die Analysen

1. **Tier-2-Benchmarking (D/E) ist noch stärker limitiert als „N=8" andeutet.**
   Eine CET1-/Leverage-/RWA-Dichte-Verteilung würde eine Exportkreditagentur mit
   einer dänischen Dorfsparkasse vergleichen — ökonomisch sinnlos. Effektive
   Peer-Gruppe ≈ 1–2. → erst Methode bauen, Insight nach Skalierung; und beim
   Skalieren muss eine Geschäftsmodell-/Größenklassen-Schichtung *vor* jedem
   Vergleich stehen.

2. **„Fehlt ≠ Null" braucht einen dritten Zustand.** Nicht nur
   `reported=true` vs. `false`, sondern auch **„strukturell nicht anwendbar"**
   (Template gar nicht im Set des Instituts, weil geschäftsmodellbedingt irrelevant).
   Ein fehlendes Marktrisiko-Template bei Rønde Sparekasse ist *erwartet*, kein
   Versäumnis.

3. **Idee A (Disclosure-Profil) wird durch die Heterogenität wertvoller, nicht
   schwächer.** Schon bei N=8 ist ein archetyp-getriebener Offenlegungs-Fußabdruck
   sichtbar. ABER: der Transparenz-Score darf **nicht** an der Gesamtzahl aller
   Templates normiert werden (sonst „bestraft" man die Sparkasse für nicht
   vorhandenes Handelsbuch-Risiko), sondern an der **geschäftsmodell-bedingten
   Anwendbarkeit**. Methodisch: Score = gemeldet / (gemeldet + bewusst als
   „nicht wesentlich/nicht anwendbar" gemeldet), nicht / Gesamtuniversum.

---

## Tier 1 — analysierbar OHNE DPM-Dictionary (jetzt/bald, unblockiert)

Diese arbeiten auf der **Struktur** (welche Templates eingereicht, Filing-Indicator,
Währung, Framework-Version), nicht auf der Semantik einzelner Datapoints. Sie
brauchen die 423-MB-Access-DB **nicht**.

### A. Disclosure-/Transparenz-Profil  ⭐ höchster Wert-zu-Aufwand
- Je Institut: wie viele Templates `true` vs `false` vs leer gemeldet.
- Welche Templates universell offengelegt werden vs. selten — „Transparenz-Score".
- **Die originellste Achse**, die der zentrale Hub überhaupt erst ermöglicht, und
  zugleich die am **wenigsten** von DPM-Labels abhängige.
- Voraussetzung: Filing-Indicator-Bug fixen. Caveat: „nicht offenlegungspflichtig"
  ≠ „freiwillig weggelassen" → braucht `frequency_of_disclosures` (Pflicht je
  Institutstyp), um Pflicht von Wahl zu trennen.
- **Wichtig:** Score an geschäftsmodell-bedingter Anwendbarkeit normieren, nicht am
  Gesamt-Template-Universum — siehe Abschnitt „Geschäftsmodell-Abhängigkeit".
  Der dritte Zustand „strukturell nicht anwendbar" muss von „bewusst weggelassen"
  getrennt werden.

### B. Framework 4.1 → 4.2 Struktur-Diff  ⭐ de-riskt Phase 3
- Beide Versionen sind bereits im Datensatz → welche Templates/Datapoints sind in
  4.2 neu/weg/verändert ggü. 4.1.
- Baut die für Zeitreihen nötige Brücke aus reiner Struktur — adressiert direkt
  das in den Instructions genannte Risiko „Versionswechsel bricht naive Zeitreihen".

### C. Währungs- & Präzisions-Landkarte (QA-Fundament)
- 3 Währungen, 3 decimals-Stufen vorhanden → validiert EUR-Normalisierung und
  decimals-Semantik, **bevor** irgendein monetärer Vergleich gezogen wird.
- Eher QA-Gate als „Analyse", aber Voraussetzung für jede Tier-2-Auswertung.

---

## Tier 2 — braucht den DPM-Join (blockiert bis Codebook steht)

### D. Kapital-/Solvenz-Benchmarking (KM1/OV1)  — das Aushängeschild
- CET1-, Leverage-, RWA-Verteilung über Institute/Länder; Quantile, Ausreißer.
- Pilot-Scope laut Instructions. Braucht: DPM-Labels + EUR-Normalisierung +
  Filing-Fix. Stichprobe noch zu klein für echtes Peer-Grouping → erst Methode,
  Insight nach Skalierung.

### E. Risiko-Komposition / Geschäftsmodell-Fingerprint
- RWA-Aufschlüsselung (Kredit-/Markt-/Op-Risiko) als Cluster-Merkmal.
- Ambitioniert: braucht DPM-Labels **und** größere Stichprobe.

### F. Kurze Zeitreihen (4 Institute)
- 4 Institute mit 2–4 Stichtagen → Kapitalquoten-Trajektorie.
- Ehrlich dünn, kreuzt zudem den 4.1→4.2-Wechsel (2026-03-31 ist 4.2) → hängt an B.
- Vorerst eher Pipeline-Test als Insight.

### G. NLP auf qualitativen PDF-Narrativen
- Boilerplate-Erkennung, Themen/Sentiment.
- Am spekulativsten: PDFs sind noch **gar nicht** ingestiert (nur XBRL-CSV-ZIPs),
  PDF-Pfad muss erst gebaut werden. Nicht überverkaufen.

---

## Empfohlene Reihenfolge

1. **Filing-Indicator-Bug fixen** (kleiner Code-Fix) — schaltet Tier 1 frei und
   repariert „Fehlt ≠ Null" für alles Weitere.
2. **A + B + C parallel zur DPM-Beschaffung** — voller Wert ohne auf die Access-DB
   zu warten; B + C sind zugleich Fundament, das Tier 2 erst vertrauenswürdig macht.
3. **D** sobald DPM-Labels stehen (Pilot KM1/OV1).
4. **E/F/G** nach Skalierung der Ingestion bzw. Aufbau des PDF-Pfads.

## Querschnitts-Caveats (in jede Analyse)
- CON vs IND nicht mischen; nationale Optionen, Rechnungslegung, Konsolidierung
  brechen naive 1:1-Vergleiche.
- 4.1 vs 4.2 nur über die Brücke (B) verbinden.
- „Fehlt" ≠ „Null" durchhalten (Filing-Indicator), erst nach Fix belastbar.
