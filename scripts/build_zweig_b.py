"""Zweig B: build the machine-readable analytics layer (Parquet via DuckDB).

Joins the long form with the DPM codebook (labels + data types), EDAP entity
metadata (name, country, EBA size class, G-SII module flag) and ECB FX rates
into ONE self-contained analytical table:

    processed/long/p3dh_long.parquet

Every row is one reported fact with everything an analysis needs attached —
no further joins required. Monetary facts carry fact_value_eur (ECB reference
rate at the reference date). Derived strictly from the long form ("the truth");
regenerate any time with:  python3 scripts/build_zweig_b.py

Quick start (DuckDB CLI or python):
    SELECT bank_name, refPeriod, fact_value*100 AS cet1_pct
    FROM 'processed/long/p3dh_long.parquet'
    WHERE template_id='61.00' AND cell_row='0050' AND cell_col='0010'
    ORDER BY cet1_pct DESC LIMIT 10;
More examples: docs/zweig_b_queries.md
"""

from pathlib import Path
import sys
import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_unit_consistency import UNIT_AMBIGUOUS_TEMPLATES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "processed" / "long"
OUT = OUT_DIR / "p3dh_long.parquet"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"SET file_search_path='{ROOT}'")

    con.execute("""
    CREATE VIEW lf AS SELECT * FROM read_csv_auto('processed/long_form_raw.csv', header=true, all_varchar=true);
    CREATE VIEW cb AS SELECT * FROM read_csv_auto('codebook/dpm_codebook.csv', header=true, all_varchar=true);
    CREATE VIEW em AS SELECT * FROM read_csv_auto('processed/entity_meta.csv', header=true, all_varchar=true);
    CREATE VIEW fx AS SELECT * FROM read_csv_auto('processed/fx_rates.csv', header=true, all_varchar=true);
    CREATE VIEW geo AS SELECT * FROM read_csv_auto('codebook/geo_names.csv', header=true, all_varchar=true);
    """)

    con.execute(f"""
    COPY (
      WITH base AS (
        SELECT
          lf.*,
          regexp_extract(lf.entityID, '([A-Z0-9]{{20}})', 1)                    AS lei,
          regexp_extract(lf.entityID, '\\.(\\w+)$', 1)                          AS scope,
          replace(lf.baseCurrency, 'iso4217:', '')                              AS currency,
          TRY_CAST(lf.fact_value AS DOUBLE)                                     AS fact_value_num,
          -- long-form template id ('60.00.A') -> DPM codebook key ('K_60.00.a')
          CASE WHEN regexp_matches(lf.template_id, '\\.[A-Z]$')
               THEN 'K_' || left(lf.template_id, length(lf.template_id)-1) || lower(right(lf.template_id,1))
               ELSE 'K_' || lf.template_id END                                  AS tcode,
          -- Open-Achsen-Dimension mit geografischem Bezug ('RIO=eba_GA:NL' ->
          -- 'NL'); andere Dimensionstypen (qEEA, GPR, ...) liefern NULL.
          regexp_extract(lf.open_axis_dims, 'eba_GA:([A-Za-z0-9]+)', 1)         AS geo_code
        FROM lf
      )
      SELECT
        b.entityID, b.lei, b.scope,
        em.name          AS bank_name,
        em.country,
        em.entity_type,
        em.institution_type,
        (em.is_gsii = 'true')                                                   AS files_gsii_module,
        b.refPeriod, b.framework_version,
        b.template_id, cb.template_title,
        b.cell_row, cb.row_label,
        b.cell_col, cb.col_label,
        b.open_axis_dims,
        geo.name          AS open_axis_country,   -- aufgelöst aus eba_GA:-Codes, sonst NULL
        b.datapoint_code,
        cb.data_type,
        b.fact_value_num          AS fact_value,
        b.fact_value              AS fact_value_raw,   -- original string: keeps ~1.3% non-numeric facts
        b.currency,
        TRY_CAST(fx.rate_to_eur AS DOUBLE)                                      AS fx_rate,
        CASE WHEN cb.data_type='monetary'
             THEN b.fact_value_num * TRY_CAST(fx.rate_to_eur AS DOUBLE)
             END                                                                AS fact_value_eur,
        -- Issue #9: Institute melden in diesen Templates nachweislich in
        -- gemischten Einheiten (manche in Basiswährung, manche in Mio) —
        -- ohne Scale-Attribut im Roh-CSV lässt sich das nicht institutsweise
        -- korrigieren. Absolutbeträge (fact_value/fact_value_eur) hier NICHT
        -- institutsübergreifend vergleichen; Quotienten bleiben unbedenklich.
        b.template_id IN ({",".join(f"'{t}'" for t in UNIT_AMBIGUOUS_TEMPLATES)}) AS unit_ambiguous,
        TRY_CAST(b.decimalsMonetary AS INTEGER)                                 AS decimals_monetary,
        b.template_reported = 'True'                                            AS template_reported,
        b.source_file
      FROM base b
      LEFT JOIN cb ON cb.datapoint_code = b.datapoint_code AND cb.template = b.tcode
                  AND cb.row = b.cell_row AND cb.col = b.cell_col
      LEFT JOIN em ON em.lei = b.lei
      LEFT JOIN fx ON fx.currency = b.currency AND fx.refdate = b.refPeriod
      LEFT JOIN geo ON geo.code = b.geo_code
    ) TO '{OUT}' (FORMAT PARQUET, COMPRESSION ZSTD);
    """)

    # Smoke tests: row count parity + a real analytical query.
    n_lf = con.execute("SELECT count(*) FROM lf").fetchone()[0]
    n_pq = con.execute(f"SELECT count(*) FROM '{OUT}'").fetchone()[0]
    print(f"✓ {OUT}  ({n_pq:,} rows, {OUT.stat().st_size/1e6:.1f} MB)")
    assert n_pq == n_lf, f"row count mismatch: parquet {n_pq} vs long form {n_lf}"

    print("\nSmoke query — Top 5 CET1-Ratio (KM1 r0050):")
    for name, date, v in con.execute(f"""
        SELECT bank_name, refPeriod, round(fact_value*100,1)
        FROM '{OUT}'
        WHERE template_id='61.00' AND cell_row='0050' AND cell_col='0010'
          AND data_type='percentage' AND abs(fact_value) <= 10
        ORDER BY 3 DESC LIMIT 5""").fetchall():
        print(f"  {str(name)[:44]:44s} {date}  {v} %")

    typed = con.execute(f"SELECT count(*) FROM '{OUT}' WHERE data_type IS NOT NULL").fetchone()[0]
    eur = con.execute(f"SELECT count(*) FROM '{OUT}' WHERE fact_value_eur IS NOT NULL").fetchone()[0]
    print(f"\n  typed: {typed:,} · EUR-normalized monetary: {eur:,}")


if __name__ == "__main__":
    main()
