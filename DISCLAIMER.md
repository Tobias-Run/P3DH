# Disclaimer & Data Sources

**Non-commercial research / educational project.** This repository is an independent,
academic data-analysis pipeline. It is **not affiliated with, endorsed by, or connected
to** the European Banking Authority (EBA), GLEIF, or any of the disclosing institutions.

## Data sources

All external data used here is **publicly available** and is used for **scientific and
educational research purposes only** (fair use / research and study exemptions):

| Source | Data | Provider |
|---|---|---|
| [EBA Pillar 3 Data Hub](https://www.eba.europa.eu/risk-and-data-analysis/pillar-3-data-hub) (via EDAP) | Public prudential disclosures (XBRL-CSV) | © European Banking Authority |
| [EBA DPM 2.0 dictionary & Annotated Table Layout](https://www.eba.europa.eu/risk-and-data-analysis/reporting-frameworks) | Datapoint / template labels | © European Banking Authority |
| [GLEIF](https://www.gleif.org/) | LEI → legal entity names | © GLEIF, CC0 |

The underlying Pillar 3 disclosures are information that credit institutions are **legally
required to publish** and that the EBA makes publicly accessible through a single portal.

## What the MIT licence covers — and what it does not

`LICENSE` (MIT) applies to the **software in this repository**: everything under
`scripts/`, `tests/`, `.github/`, the viewer (`processed/zweig_a/viewer_json.html`),
the landing pages, and the prose written for this project (`README.md`, `docs/`).

It does **not** — and cannot — apply to material derived from third-party sources:

| Path | Content | Governed by |
|---|---|---|
| `codebook/dpm_codebook.csv`, `codebook/template_titles.csv` | Datapoint and template labels from the EBA DPM 2.0 dictionary | © European Banking Authority — see sources above |
| `interim/edap_recon/manifest_*.csv` | Submission catalogue harvested from EDAP | © European Banking Authority |
| `processed/lei_names.csv`, `processed/entity_meta.csv` | Legal entity names via GLEIF | © GLEIF, CC0 |
| The published dataset (`data` branch, release assets) | Re-presented Pillar 3 disclosures | © European Banking Authority |

We hold no rights in that material and grant none. It is included and
redistributed here under the research/education terms set out on this page; reuse
is subject to the original providers' conditions, not to the MIT licence.

## Terms of use of this repository

- **Research use.** The processed data and viewer are provided for transparency research,
  education, and reproducibility — **not** for commercial redistribution of the source data.
- **No warranty.** Data is provided *"as is"*. This pipeline parses and re-presents the
  original filings and **may contain errors** (parsing, mapping, currency, or scaling).
  Always verify against the **official EBA source** before relying on any figure.
- **Not advice.** Nothing here is investment, financial, legal, or accounting advice.
- **Attribution.** When reusing derived outputs, please attribute the original data to the
  EBA (and GLEIF for entity names) and link back to the official sources above.
- **Takedown.** If a rights holder considers any content inappropriate for inclusion, please
  open an issue and it will be addressed promptly.

## Comparability caveats

Figures across institutions are **not naïvely comparable**: accounting frameworks,
consolidation scope (CON/IND), national options, reporting currency (EUR/SEK/DKK/…), and
reporting-framework version (4.1 vs 4.2) differ. Treat cross-entity comparisons with care.
