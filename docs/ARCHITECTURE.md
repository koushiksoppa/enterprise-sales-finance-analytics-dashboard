# Architecture

```
                 ┌───────────────────┐
                 │   Raw Source Data  │   data/raw/*.csv
                 │ (messy, realistic) │
                 └─────────┬─────────┘
                           │  python/generate_sample_data.py
                           ▼
                 ┌───────────────────┐
                 │   Python ETL       │   python/clean_data.py
                 │ clean · dedupe ·   │   - type fixes, null handling
                 │ engineer features  │   - dedupe, referential integrity
                 └─────────┬─────────┘
                           ▼
                 ┌───────────────────┐
                 │ Star Schema CSVs   │   data/processed/*.csv
                 │ Dim*/Fact tables   │
                 └───┬───────────┬───┘
                     │           │
        python/prepare_sql_csv  │  python/build_kpis.py
                     │           │
                     ▼           ▼
        ┌────────────────┐  ┌────────────────────┐
        │  SQL Server DW  │  │  reports/*.csv +    │
        │  sql/*.sql      │  │  executive_insights │
        │  star schema,   │  │  .md                │
        │  views, KPIs    │  └────────────────────┘
        └───────┬─────────┘
                │  BULK INSERT (sql/02_load_data.sql)
                ▼
        ┌─────────────────────────────┐
        │  Power BI Desktop            │
        │  Power Query M (import CSV   │
        │  or SQL views) → Model →     │
        │  DAX measures → 6 report     │
        │  pages → .pbix               │
        └─────────────────────────────┘
```

## Layers

1. **Data generation** (`python/generate_sample_data.py`) — produces a
   realistic, intentionally messy raw dataset (duplicates, nulls, invalid
   quantities) so the cleaning layer has genuine work to do.
2. **ETL / cleaning** (`python/clean_data.py`) — deduplicates, fixes types,
   enforces referential integrity, engineers `profit`, `profit_margin_pct`,
   and builds a proper `DimDate` calendar table. Outputs a clean star schema
   to `data/processed/`.
3. **SQL data warehouse** (`sql/*.sql`) — DDL for the star schema with
   indexes, a bulk-load script from the processed CSVs, and analytical
   queries (joins, CTEs, window functions, views) that mirror what the
   Power BI DAX layer computes — useful both as a validation cross-check and
   as a standalone reporting layer for tools other than Power BI.
4. **KPI & insight layer** (`python/build_kpis.py`,
   `python/generate_insights.py`) — computes growth, ranking, and turnover
   KPI tables and turns them into a plain-English executive insights report.
5. **Power BI** (`powerbi/`) — Power Query M scripts, DAX measures/columns,
   a custom theme, and a step-by-step build guide to assemble the `.pbix`
   with six dashboard pages, slicers, bookmarks, drill-through, and
   tooltips.

## Why the pipeline is split this way
Each stage writes its output to disk and can be re-run independently,
mirroring how a real BI team separates ingestion, transformation, and
presentation. It also means the SQL warehouse and the Power BI report can be
rebuilt from the same processed CSVs without re-running the whole pipeline.
