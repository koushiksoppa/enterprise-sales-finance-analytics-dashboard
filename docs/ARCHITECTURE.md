# Architecture

```
                 ┌────────────────────┐
                 │   Raw Source Data   │   data/raw/*.csv
                 │ (messy, realistic)  │
                 └──────────┬─────────┘
                            │  python/generate_sample_data.py
                            ▼
                 ┌────────────────────┐
                 │    Python ETL       │   python/clean_data.py
                 │ clean · dedupe ·    │   - type fixes, null handling
                 │ engineer features   │   - dedupe, referential integrity
                 └──────────┬─────────┘
                            ▼
                 ┌────────────────────┐
                 │  Star Schema CSVs   │   data/processed/*.csv
                 │  Dim* / Fact tables │
                 └───┬────────────┬───┘
                     │            │
     python/prepare_sql_csv.py    │  python/build_kpis.py
                     │            │
                     ▼            ▼
        ┌────────────────┐  ┌──────────────────────────┐
        │  SQL Server DW  │  │   reports/kpi_*.csv       │
        │  sql/*.sql      │  │   (12 KPI tables)         │
        │  star schema,   │  └───┬──────────────────┬───┘
        │  views, KPIs    │      │                  │
        └───────┬─────────┘      │                  │
                │                ▼                  ▼
                │   python/generate_insights   python/build_dashboard
                │        .py                        _previews.py
                │        │                          │
                │        ▼                          ▼
                │   reports/executive_          screenshots/*.svg
                │   insights.{md,html}          (six report pages)
                │
                │  BULK INSERT (sql/02_load_data.sql)
                ▼
        ┌──────────────────────────────┐
        │  Power BI Desktop             │
        │  Power Query M (import CSV    │
        │  or SQL views) → Model →      │
        │  DAX measures → 6 report      │
        │  pages → .pbix                │
        └──────────────────────────────┘
```

## Layers

1. **Data generation** (`python/generate_sample_data.py`) — produces a
   realistic, intentionally messy raw dataset (duplicates, nulls, invalid
   quantities) so the cleaning layer has genuine work to do.
2. **ETL / cleaning** (`python/clean_data.py`) — deduplicates, fixes types,
   enforces referential integrity, engineers `profit` and
   `profit_margin_pct`, and builds a `DimDate` calendar table. Outputs a clean
   star schema to `data/processed/`.
3. **SQL data warehouse** (`sql/*.sql`) — DDL for the star schema with indexes,
   a bulk-load script, analytical queries (joins, CTEs, window functions), and
   reporting views. It serves both as a validation cross-check on the BI layer
   and as a standalone reporting layer for tools other than Power BI.
4. **KPI layer** (`python/build_kpis.py`) — twelve KPI tables written to
   `reports/`, covering the headline summary, monthly trend, product, customer,
   region, country, category and segment performance, inventory risk, and the
   revenue forecast.
5. **Insight layer** (`python/generate_insights.py`) — turns those tables into
   an executive report in Markdown and styled HTML. Both formats render from
   one set of findings so they cannot disagree.
6. **Preview layer** (`python/build_dashboard_previews.py`) — renders each of
   the six report pages as an SVG at Power BI's 1280×720 canvas size, using the
   real KPI values.
7. **Power BI** (`powerbi/`) — Power Query M, DAX measures and columns, the
   report theme, and a build guide that specifies every visual's position.

## Cross-cutting pieces

**`docs/KPI_DEFINITIONS.md`** is the contract between the Python, SQL and DAX
implementations of each KPI. Margin weighting, the margin health bands, the
reorder risk bands and the treatment of data-quality buckets are written once
there and implemented identically in all three.

**`python/report_theme.py`** holds the palette and the number formatters shared
by the insights report and the previews. It mirrors `powerbi/theme.json`, so
the generated deliverables and the Power BI report use the same colour for the
same meaning. Change one and change the other.

## Why the pipeline is split this way

Each stage writes its output to disk and can be re-run independently, mirroring
how a real BI team separates ingestion, transformation and presentation. The
SQL warehouse and the Power BI report can both be rebuilt from the same
processed CSVs without re-running the whole pipeline, and the reporting and
preview layers depend only on `reports/`, not on the raw data.

## Dependency order

```
generate_sample_data  →  clean_data  →  prepare_sql_csv  →  (SQL load)
                             ↓
                         build_kpis  →  generate_insights
                                     →  build_dashboard_previews
```

`prepare_sql_csv.py` rewrites `DimDate.csv` in place (column order, and
`is_weekend` as 1/0 for the SQL `BIT` column), so run it before loading either
SQL Server or Power BI — the Power Query script expects the normalised form.
