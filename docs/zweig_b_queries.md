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
GROUP BY 1 ORDER BY 2 DESC;
```
⚠️ `open_axis_country IS NULL` heißt nicht „fehlerhaft" — die Codes `eba_GA:x1`/`x28`
sind EBA-eigene Aggregat-Codes (vermutlich „übrige Länder"), nicht in ISO 3166-1,
bisher unaufgelöst.

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
