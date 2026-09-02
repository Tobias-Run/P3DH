# Zweig B — Analytics mit DuckDB

Bauen: `python3 scripts/build_zweig_b.py` → `processed/long/p3dh_long.parquet`
(eine selbsterklärende Faktentabelle: Labels, Datentypen, Bank-Metadaten und
EUR-Normalisierung sind bereits angejoint — keine weiteren Joins nötig).

Nutzen (CLI `duckdb` oder `python3 -c "import duckdb; ..."`), Pfade relativ zum Repo-Root.

## Spalten (Auswahl)

`bank_name, lei, scope (CON/IND), country, institution_type, files_gsii_module,
refPeriod, framework_version, template_id, template_title, cell_row, row_label,
cell_col, col_label, open_axis_dims, open_axis_country, datapoint_code, data_type,
fact_value, fact_value_raw, currency, fx_rate, fact_value_eur, unit_ambiguous,
template_reported, source_file`

`fact_value` ist numerisch gecastet (NULL bei Textfakten); `fact_value_raw` hält den
Original-String (inkl. der ~1,3 % nicht-numerischen Text-/Enum-Fakten). `fx_rate` ist
der EZB-Kurs zum Stichtag (Basis für `fact_value_eur`). Diese Parquet-Tabelle speist
auch den JSON-Viewer (Zweig A) — via `build_zweig_a_shards.py`.

## Beispiele

**CET1-Rangliste (KM1 r0050):**
```sql
SELECT bank_name, refPeriod, round(fact_value*100,1) AS cet1_pct
FROM 'processed/long/p3dh_long.parquet'
WHERE template_id='61.00' AND cell_row='0050' AND cell_col='0010'
  AND abs(fact_value) <= 10          -- Fehlfilings (Beträge in Ratio-Zeilen) raus
ORDER BY cet1_pct DESC;
```

**Aggregierte TREA je Land (EZB-kursnormalisiert, Mrd. EUR):**
```sql
SELECT country, round(sum(fact_value_eur)/1e9,1) AS trea_mrd_eur, count(*) AS banken
FROM 'processed/long/p3dh_long.parquet'
WHERE template_id='61.00' AND cell_row='0040' AND cell_col='0010'
GROUP BY country ORDER BY trea_mrd_eur DESC;
```

**Zeitreihe einer Bank (alle KM1-Kennzahlen):**
```sql
SELECT refPeriod, row_label, fact_value, data_type
FROM 'processed/long/p3dh_long.parquet'
WHERE lei='1FOLRR5RWTWWI397R131' AND template_id='61.00' AND cell_col='0010'
ORDER BY cell_row, refPeriod;
```

**Offene-Achsen-Daten mit aufgelöstem Land + Metrik (CCyB1, Template 67.01.A):**
`open_axis_country` löst `RIO=eba_GA:NL` -> `Niederlande` auf (98,2 % der 181.696
Fakten mit `eba_GA:`-Dimension über vier Templates: 67.01.A, 83.01.C/D, 45.00.A/B,
66.02.A). `row_label`/`col_label`/`data_type`/`fact_value_eur` sind für offene
Achsen zusätzlich über einen Fallback auf global eindeutige dp-Codes im Codebook
aufgelöst (Issue #10) — für 67.01.A 70 % der Fakten (93.699 von 134.302):
```sql
SELECT open_axis_country, SUM(fact_value_eur)/1e9 AS mrd_eur
FROM 'processed/long/p3dh_long.parquet'
WHERE template_id='67.01.A' AND datapoint_code IN ('dp149275','dp148983')  -- Exposure SA + IRB
  AND lei='0W2PZJM8XOY22M4GG883' AND refPeriod='2025-12-31'
  AND open_axis_country IS NOT NULL        -- ⚠️ PFLICHT, sonst Doppelzählung (s. u.)
GROUP BY 1 ORDER BY 2 DESC;
```

🚨 **`eba_GA:x1` ist die Summenzeile „Total", kein Land.** Empirisch belegt: bei
89 von 96 Instituten, die diesen Bucket melden, gilt exakt
`x1 = Summe(benannte Länder) + x28` (Median-Verhältnis 1,000). Wer die
`open_axis_country IS NULL`-Zeilen mitsummiert, **zählt das Gesamtexposure
doppelt** — im Beispiel oben wäre der größte „Posten" mit 34 Mrd EUR schlicht
die Gesamtsumme. Immer `open_axis_country IS NOT NULL` filtern oder `x1`
gezielt als Kontrollsumme verwenden.

`eba_GA:x28` ist dagegen ein echter Residual-Bucket („übrige Länder"); seine
Belegung schwankt stark je Melder (bei manchen Instituten liegt dort fast das
gesamte Exposure). Beide Codes stehen nicht in ISO 3166-1 und bleiben in
`open_axis_country` bewusst `NULL`.

**Restlücke (Issue #10):** Der Fallback wirkt nur für dp-Codes, die **global
eindeutig** im Codebook stehen (nur eine `(template,row,col)`-Kombination über
alle Templates). Für 67.01.A bleiben 4 von 13 dp-Codes unaufgelöst (`row_label
IS NULL`), darunter die beiden mengenmäßig größten. `83.01.C`/`83.01.D` haben
**keinen** Treffer unter irgendeinem Template — fehlende Codebook-Abdeckung wie
in #3, kein Fallback-Problem.

**Einheiten-Sperrliste (`unit_ambiguous`):** In den Templates `41.00` und
`45.00.A` melden Institute nachweislich in gemischten Einheiten (manche in
Basiswährung, manche in Millionen — siehe `docs/phase4_analysis_ideas.md`,
Issue #9). `unit_ambiguous=true` markiert alle monetären Zellen dieser
Templates; `fact_value`/`fact_value_eur` dort **nicht** institutsübergreifend
vergleichen, nur Quotienten innerhalb desselben Reports bilden:
```sql
SELECT bank_name, fact_value AS gross_carrying_amount   -- Einheit je Report unklar!
FROM 'processed/long/p3dh_long.parquet'
WHERE unit_ambiguous AND template_id='41.00' AND cell_row='0010' AND cell_col='0010';
-- Systematischer Scan über alle monetären Templates: scripts/check_unit_consistency.py
```

**Plausibilität gegen die Population (`quality_profile.csv`, Issue #17):**
`scripts/check_plausibility.py` misst jeden Wert an der Population **seiner
eigenen Zelle** (Median/MAD auf log10, monetär in EUR) statt an einer globalen
Schranke, und ergänzt fachliche Korridore auf abgeleiteten Verhältnissen.
Ergebnis: 3.224 Befunde in 226 von 553 Reports.

```sql
-- Werte in einer Rangliste vorab entschärfen: auffällige Reports markieren
SELECT p.bank_name, p.refPeriod, p.n_findings, p.findings_per_1000, p.templates
FROM read_csv_auto('processed/quality_profile.csv', header=true) p
WHERE p.n_hoch > 0 ORDER BY p.findings_per_1000 DESC;
```

⚠️ **`n_findings` ist keine Rangliste der Meldequalität.** Wer 136 Templates
meldet, hat mehr Gelegenheiten aufzufallen als wer 4 meldet — dafür ist
`findings_per_1000` (je 1.000 tatsächlich prüfbarer Fakten) da. Und ein
Ausreißer kann eine korrekte Besonderheit sein; der Check sagt „passt nicht
zur Population", nicht „ist falsch".

Drei Dinge, die beim Nachnutzen zählen:

- **Nur die obere Flanke** wird statistisch geprüft. Die untere ist bei
  Exposure-Daten natürlich (viele Institute haben nahe null Exposure zu einer
  Kategorie); symmetrisch geprüft waren 9.750 von 12.744 Befunden Rauschen,
  darunter Rundungsreste wie `1,7·10⁻¹¹` EUR. Die untere Flanke deckt statt-
  dessen `RATIO_RULES` mit fachlichem Wissen ab — dort fällt z. B. auf, wenn
  ein Institut REM1 in Millionen meldet.
- **`plausibility_cells.csv` mit `status='unbrauchbar'`** (199 Zellen) listet
  Zellen, deren Rumpf über ≥ 6 Größenordnungen streut. Dort ist unklar, welche
  Lesart gilt — kein Institut wird belastet, und diese Zellen taugen auch für
  eigene Auswertungen nicht. Beispiel `09.05` c0020 („Of which exposures in
  default", als `percentage` typisiert): 303 Werte ≤ 1 gegen 316 > 1.
- Belegte Funde daraus: Rabobank meldet REM1 `30.01` mit 11,7 Bio. EUR fixer
  Vergütung für 9 Vorstandsmitglieder (vom Gap-Scan aus #9 **nicht** gefunden,
  weil dort keine scharfe Lücke liegt), DNB meldet PD als `100.000.000` statt
  `1,0` (populationsweit 228 PD-Zellen mit > 100 % Ausfallwahrscheinlichkeit),
  und Česká spořitelna füllt die Quotenzeile `61.00` r0200 mit einem Betrag.

**Disclosure-Coverage („fehlt ≠ Null") kommt aus der zweiten Datei:**
```sql
SELECT entityID, count(*) FILTER (reported='True')  AS reported,
                 count(*) FILTER (reported='False') AS declared_not
FROM read_csv_auto('processed/filing_indicators.csv', header=true)
GROUP BY entityID ORDER BY declared_not DESC;
```

## Hinweise

- `fact_value_eur` ist nur für `data_type='monetary'` gefüllt (EZB-Referenzkurs
  zum Stichtag, Quelle `processed/fx_rates.csv`).
- Ratios stehen als Dezimalzahl in `fact_value` (0.235 = 23,5 %).
- Vergleichbarkeits-Caveats beachten (`DISCLAIMER.md`): Konsolidierungskreis,
  Rechnungslegung, nationale Optionen, Framework 4.1/4.2.
