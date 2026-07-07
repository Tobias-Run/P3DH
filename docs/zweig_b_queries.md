# Zweig B — Analytics mit DuckDB

Bauen: `python3 scripts/build_zweig_b.py` → `processed/long/p3dh_long.parquet`
(eine selbsterklärende Faktentabelle: Labels, Datentypen, Bank-Metadaten und
EUR-Normalisierung sind bereits angejoint — keine weiteren Joins nötig).

Nutzen (CLI `duckdb` oder `python3 -c "import duckdb; ..."`), Pfade relativ zum Repo-Root.

## Spalten (Auswahl)

`bank_name, lei, scope (CON/IND), country, institution_type, files_gsii_module,
refPeriod, framework_version, template_id, template_title, cell_row, row_label,
cell_col, col_label, open_axis_dims, datapoint_code, data_type, fact_value,
currency, fact_value_eur, template_reported, source_file`

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

**Offene-Achsen-Daten (z. B. CCyB nach Land, Template 67.01):**
```sql
SELECT bank_name, open_axis_dims, fact_value
FROM 'processed/long/p3dh_long.parquet'
WHERE template_id LIKE '67.01%' AND open_axis_dims LIKE '%RIO=%';
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
