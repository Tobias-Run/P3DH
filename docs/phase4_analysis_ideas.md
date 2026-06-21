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
3. **Kleine Stichprobe** — 8 Institute tragen kein robustes Peer-Benchmarking /
   Clustering. Querschnitt-Analysen sind vorerst „Methode bauen, Insight nach
   Skalierung der Ingestion".

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
