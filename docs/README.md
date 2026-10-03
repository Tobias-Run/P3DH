# Documentation index

**[Open the live Pillar 3 Viewer →](https://tobias-run.github.io/P3DH/processed/zweig_a/viewer_json.html)**

Start with the [project README](../README.md) for installation, repository layout
and the pipeline. The documents below explain decisions, data semantics and
validation. German-language documents are marked where applicable.

## Status and reviews

- [Issue review — 2 October 2026](issue_review_2026-10-02.md) *(German)*:
  all 73 reviewed tickets, evidence links and remaining work at that date.
- [Project inventory](../STATUS.md): dated inventory of data and implemented features.
- [Decision history](../BACKLOG.md): findings and past scope decisions.
- [GitHub issues](https://github.com/Tobias-Run/P3DH/issues): current work and discussion.

## Data and pipeline

- [Scope and access](phase0_decision_memo.md)
- [Ingestion](phase1_ingestion.md)
- [XBRL-CSV format notes](xbrl_csv_format_notes.md)
- [Framework bridge](phase3_framework_bridge.md)
- [Dataset description](datensatz.md) *(German)*
- [Reproducibility](reproduzierbarkeit.md) *(German)*
- [Release procedure](release.md) *(German)*
- [DuckDB query examples](zweig_b_queries.md) *(German)*
- [Disclaimer and source rights](../DISCLAIMER.md)

## Viewer and performance

- [Advanced peer groups and ownership research](advanced_peers/REPORT.md) *(German, draft)*

- [Viewer design](viewer_redesign.md) *(German)*
- [Performance review](performance_review.md) *(German)*
- [Performance implementation](performance_implementation.md) *(German)*
- [Measurement tools and reproducible experiments](../performance/README.md)
- [KPI source navigation](kpi_source_navigation/REPORT.md)
- [Exact KPI source cells](kpi_source_cells/REPORT.md)
- [KPI units](kpi_metric_units/REPORT.md)
- [UI and template group localization](ui_localization/REPORT.md)
- [Scale findings review — 1 October 2026](scale_review_2026-10-01/REPORT.md)

## Analyses and historical context

- [Analyses after the full load](analysen_nach_vollload.md) *(German)*
- [The Correction Game](korrekturspiel.md) *(German)*
- [Research gaps](forschungsluecken.md) *(German)*
- [Added value compared with EDAP](mehrwert_vs_edap.md) *(German)*
- [Further analysis ideas](phase4_analysis_ideas.md)
- [Original project brief](projektbriefing_2026-06.txt) *(German, historical)*
- [Earlier issue review](issue_review.md) *(historical)*
- [Official EDAP visualization guide](EBA_UserGuide_EDAP_visualisation_tools.pdf)

Reports describe the revision and date they tested. Raw measurements, screenshots,
profiles and validation logs are retained alongside the reports or under
`performance/results/`; they are evidence, not disposable caches. Downloaded
datasets, generated viewer shards and local Python caches remain outside version
control.
