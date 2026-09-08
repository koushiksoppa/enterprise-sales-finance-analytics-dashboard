# Enterprise Sales & Finance Analytics Dashboard

An end-to-end Business Intelligence project. A synthetic-but-realistic retail
dataset flows through a Python ETL pipeline into a SQL Server star schema and a
six-page Power BI executive dashboard, with an automatically generated
executive insights report layered on top.

![Executive Dashboard](screenshots/executive_dashboard.svg)

## Overview

| Layer | Tech | What it does |
|---|---|---|
| Data generation | Python (pandas, numpy) | Produces a realistic, intentionally messy sample dataset |
| ETL | Python | Cleans, deduplicates, type-fixes, and engineers a star schema |
| Data warehouse | SQL Server (T-SQL) | Star schema DDL, indexes, views, KPI queries with joins, CTEs and window functions |
| KPI layer | Python | Twelve KPI tables that back the report and cross-check the DAX |
| BI layer | Power BI Desktop | Six-page dashboard: DAX measures, Power Query, theme, bookmarks, drill-through, tooltips |
| Insights | Python | Executive insights report in Markdown and print-ready HTML |
| Previews | Python | Data-driven SVG renders of all six report pages |

`docs/ARCHITECTURE.md` has the full data-flow diagram.
`docs/KPI_DEFINITIONS.md` is the contract that keeps the Python, SQL and DAX
implementations of each KPI in agreement.

## Dashboard pages

Every page answers one question and is laid out on the same grid.

| Page | Question it answers |
|---|---|
| Executive Dashboard | How is the business performing? |
| Sales Analytics | Where are sales coming from and what drives them? |
| Financial Analytics | Are we growing profitably? |
| Customer Analytics | Who are our customers and how do they behave? |
| Inventory Analytics | Where are we exposed to inventory risk? |
| Forecast Dashboard | What is likely to happen next? |

All six share a navigation bar, a synced slicer strip (year, region, category,
segment), bookmark presets, drill-through to a product detail page, and report
page tooltips.

<details>
<summary><b>Sales Analytics</b> — trend and 3-month average, AOV by category, top products, region and segment mix</summary>

![Sales Analytics](screenshots/sales_analytics.svg)
</details>

<details>
<summary><b>Financial Analytics</b> — profit trend, margin by category against the 35% healthy band, lowest-margin products with status</summary>

![Financial Analytics](screenshots/financial_analytics.svg)
</details>

<details>
<summary><b>Customer Analytics</b> — base growth, revenue by segment, top customers, revenue per customer</summary>

![Customer Analytics](screenshots/customer_analytics.svg)
</details>

<details>
<summary><b>Inventory Analytics</b> — stock against reorder level, turnover by product, replenishment watchlist</summary>

![Inventory Analytics](screenshots/inventory_analytics.svg)
</details>

<details>
<summary><b>Forecast Dashboard</b> — actuals, trend, moving average and a six-month projection with its range</summary>

![Forecast Dashboard](screenshots/forecast_dashboard.svg)
</details>

The previews are rendered from the KPI tables by
`python/build_dashboard_previews.py`, on the same 1280×720 canvas Power BI uses,
so the numbers on them are the pipeline's actual output and the panel
coordinates double as the layout specification in
`powerbi/POWERBI_BUILD_GUIDE.md`.

Each SVG carries both colour schemes: the light palette sits on every element
as a presentation attribute, and an embedded stylesheet swaps in the dark
palette under `prefers-color-scheme: dark`. Text and chart series are separate
tokens, so in dark mode headings invert to near-white while the navy series
brightens to a legible blue rather than disappearing into the background.
The scheme follows the reader's browser or OS preference, which is not
necessarily the same as a site's own light/dark toggle.

## Folder structure

```
enterprise-sales-finance-analytics-dashboard/
├── data/
│   ├── raw/             # generated raw CSVs (messy, pre-cleaning)
│   └── processed/       # cleaned star-schema CSVs
├── sql/                 # DDL, bulk load, analytical queries, views
├── python/              # ETL, KPI, insights, and preview scripts
├── powerbi/             # DAX, Power Query M, theme, build guide
├── docs/                # architecture, dataset, KPI definitions, installation
├── screenshots/         # generated preview of each report page
├── reports/             # generated KPI tables + executive insights (MD + HTML)
├── README.md
├── requirements.txt
└── LICENSE
```

## Dataset

19,665 cleaned order-line transactions (January 2022 – December 2024) across
500 customers, 22 products in 5 categories, and 10 countries in 4 regions,
generated with a fixed random seed for reproducibility. Full details in
`docs/DATASET.md`.

Headline figures from the shipped run: **$103.1M revenue, $50.7M profit, 49.2%
margin, $5,244 average order value, +7.0% revenue growth 2023 → 2024.**

## KPIs

Revenue · Profit · Profit Margin % · Sales Growth MoM/YoY · Average Order Value
· Customer Growth % · Repeat Customer Rate · Inventory Turnover Ratio · Top
Products · Top Customers · Regional Performance.

Each is implemented three times — as a DAX measure
(`powerbi/DAX/measures.dax`), as T-SQL (`sql/03_analysis_queries.sql`,
`sql/04_views.sql`), and in Python (`python/build_kpis.py`) — from a single
written definition in `docs/KPI_DEFINITIONS.md`, including the margin health
bands, the reorder risk bands, and the rule that all margins are
revenue-weighted.

## Installation

Full walkthrough in `docs/INSTALLATION.md`.

### 1. Environment

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run the pipeline

```powershell
python python\generate_sample_data.py
python python\clean_data.py
python python\prepare_sql_csv.py
python python\build_kpis.py
python python\generate_insights.py
python python\build_dashboard_previews.py
```

Run them in that order — each stage reads the previous stage's output. This
populates `data/raw/`, `data/processed/`, `reports/` and `screenshots/`. Open
`reports/executive_insights.html` to check the run.

### 3. Build the `.pbix`

A `.pbix` is a proprietary binary that only Power BI Desktop can write, so this
stage is manual — roughly 45–60 minutes of wiring, with no design decisions
left to make. `powerbi/POWERBI_BUILD_GUIDE.md` gives the full detail; the
sequence is:

1. **Theme** — View → Themes → Browse for themes → `powerbi/theme.json`.
2. **Parameter** — Home → Transform data → Manage Parameters → New: `FolderPath`,
   Text, set to your absolute path to `data\processed\` (trailing backslash
   required).
3. **Queries** — one Blank Query per table (`DimDate`, `DimCustomer`,
   `DimProduct`, `DimRegion`, `DimInventory`, `FactSales`); paste the matching
   block from `powerbi/PowerQuery/power_query_m.pq` into the Advanced Editor,
   rename to the table name, then Close & Apply.
4. **Model** — create the six relationships in the guide's table, marking
   `DimCustomer[signup_date] → DimDate[full_date]` **inactive**, then Mark
   `DimDate` as a Date Table on `full_date`.
5. **DAX** — paste the measures from `powerbi/DAX/measures.dax` and the columns
   from `powerbi/DAX/calculated_columns.dax`. Add `DimDate[Month Index]` before
   the trend measures, which depend on it.
6. **Pages** — create the six pages and place each visual at the coordinates in
   the guide. They are the same coordinates the previews in `screenshots/` were
   rendered at, so you can compare a finished page against its preview.
7. **Interactivity** — sync the four slicers across pages, add the bookmark
   presets, the `Product Detail` drill-through page, and the tooltip page.
8. **Save** as `powerbi/Enterprise_Sales_Finance_Dashboard.pbix`. Run
   `git lfs install` first — `.gitattributes` already tracks `*.pbix`.

### 4. SQL warehouse (optional)

Run `sql/01_schema.sql`, set `@DataPath` in `sql/02_load_data.sql` to your
`data\processed\` path and run it, then `sql/04_views.sql` and
`sql/03_analysis_queries.sql`. The query results should match the
corresponding files in `reports/`.

## Executive insights

`python/generate_insights.py` reads the KPI tables and writes
`reports/executive_insights.md` and `reports/executive_insights.html` (styled
and print-ready) from one set of findings, so the two cannot disagree. Every
figure is read from a KPI table; nothing is hand-written.

The report covers regional and category performance, profitability and margin
outliers, customer behaviour, inventory risk, a six-month outlook with its
method stated, prioritised recommendations, and a data-quality section. Like
the previews it follows the reader's light or dark preference, and reverts to
the light palette when printed.

Two design decisions in that generator are worth calling out, because they are
the difference between a report and a plausible-looking report:

- **Data-quality buckets are excluded from rankings.** Revenue whose source
  region failed referential integrity sits in an `Unknown / Unassigned` bucket
  and customers with a blank segment in an `Unclassified` bucket. Both are
  reported in the totals and named in the data-quality section, but neither can
  be returned as "the worst-performing region" or "the segment to invest in".
- **Findings adapt to what the data shows.** Where a metric is saturated or a
  spread is immaterial, the report says so and points at the measure that does
  carry signal, instead of asserting a conclusion the numbers do not support.

## Notes on the data

Because the dataset is synthetic and orders are assigned to customers
uniformly at random, two metrics behave unlike a real transactional extract and
the reporting layer states this rather than working around it:

- **Repeat Customer Rate reads 100%.** Every customer has ordered many times
  (39.3 orders each on average), so the metric is saturated. Orders per customer
  is the informative depth measure on this dataset.
- **Revenue concentration is very low.** The top 10 customers hold 3.1% of
  revenue, so there is no Pareto tail to analyse.

Both are properties of the generator, not analytical errors, and both are
documented in `docs/KPI_DEFINITIONS.md`. Swapping in a real extract restores
normal behaviour without changing any downstream logic.

## Future improvements

- Swap the synthetic dataset for a real transactional export
- Give the generator realistic customer purchase concentration so the retention
  and concentration metrics carry signal
- Add Row-Level Security roles in Power BI for regional managers
- Automate the ETL with a scheduled task or Azure Data Factory pipeline
- Publish to the Power BI Service with a scheduled refresh
- Add a paginated-report version for print-friendly exports

## What this project demonstrates

| Capability | Where to look |
|---|---|
| **Data modelling** | Star schema, 5 dimensions and a 19,665-row fact table. `DimRegion` is at country grain, and the region rollup is handled explicitly rather than by accident — `docs/DATASET.md` |
| **ETL and data quality** | Deduplication, referential-integrity repair, type coercion and feature engineering over an intentionally messy source — `python/clean_data.py` |
| **KPI governance** | One written definition per KPI, implemented three times — Python, T-SQL and DAX — and reconciled to the same totals: `docs/KPI_DEFINITIONS.md` |
| **SQL / T-SQL** | Joins, CTEs, window functions (`LAG`, `RANK`, running totals) and six reporting views — `sql/03_analysis_queries.sql`, `sql/04_views.sql` |
| **DAX** | 44 measures and 11 calculated columns: time intelligence, ranking, status banding and a least-squares trend — `powerbi/DAX/` |
| **Forecasting** | Seasonal linear-trend projection with a residual-based range, compared year-on-year so seasonality is not misread as decline — `python/build_kpis.py` |
| **Automated insights** | A written executive briefing generated from the KPI tables in Markdown and print-ready HTML — `python/generate_insights.py` |
| **Analytical judgement** | Data-quality buckets excluded from rankings; saturated metrics flagged rather than presented as findings — `reports/executive_insights.md` |
| **BI delivery and design** | Six-page report on a documented design system: theme, per-visual layout, synced slicers, bookmarks, drill-through, tooltips — `powerbi/POWERBI_BUILD_GUIDE.md` |

## Resume description

> Built an end-to-end Business Intelligence solution (Python, SQL Server,
> Power BI): a star-schema data warehouse, an ETL pipeline that cleaned and
> validated ~20K transactional records, and a governed KPI layer implemented
> identically in Python, T-SQL and DAX from a single written definition.
> Authored the complete Power BI implementation for a six-page executive
> dashboard — Power Query M ingestion, the data model, 44 DAX measures, a
> report theme and per-visual layout — covering drill-through, synced
> filtering and a six-month seasonal revenue forecast, with every page
> rendered from live KPI output so the design is verifiable against real
> numbers. Automated the reporting cycle with an executive insights briefing
> generated directly from the KPI tables. Diagnosed and fixed a dimension-grain defect that had
> split one region into three and understated the leading region's revenue by
> 2.5x, and built reconciliation checks so every KPI table ties to the same
> totals.

## License

MIT — see `LICENSE`.
