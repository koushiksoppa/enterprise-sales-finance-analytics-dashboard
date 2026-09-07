# Dataset Description

The sample dataset is synthetically generated (`python/generate_sample_data.py`,
seeded with `RANDOM_SEED = 42` for reproducibility) to resemble a mid-size
B2B/B2C hardware and software retailer operating across four global regions. It
is deliberately "messy" — duplicate rows, missing values and invalid quantities
— so the cleaning pipeline demonstrates real data-engineering work rather than
operating on already-perfect data.

## Raw tables (`data/raw/`)

| File | Rows | Description |
|---|---|---|
| `regions.csv` | 11 | Region/country reference, including the `R00` unknown bucket |
| `customers.csv` | 510 | Customer master, with ~2% duplicate rows, ~3% missing names, ~2% blank segments, ~1% invalid region |
| `products.csv` | 22 | Product catalog across 5 categories |
| `inventory.csv` | 22 | Stock level per product per warehouse |
| `sales_transactions.csv` | 20,200 | Order-line grain sales, 2022–2024, with ~1.5% invalid quantities, ~1% missing revenue and ~1% duplicate rows |

## Processed star schema (`data/processed/`)

| Table | Rows | Grain | Key columns |
|---|---|---|---|
| `DimDate` | 1,096 | 1 row per day | `date_id` (YYYYMMDD int PK), calendar attributes, `fiscal_year` |
| `DimCustomer` | 500 | 1 row per customer | `customer_id` PK, `segment`, `region_id` FK, `signup_date` |
| `DimProduct` | 22 | 1 row per product | `product_id` PK, `category`, `unit_cost`, `unit_price`, `margin_pct` |
| `DimRegion` | 11 | **1 row per country** | `region_id` PK, `region_name`, `country` |
| `DimInventory` | 22 | 1 row per product/warehouse | `product_id` FK, `stock_quantity`, `reorder_level`, `needs_reorder` |
| `FactSales` | 19,665 | 1 row per order line | `order_id` PK, `date_id`/`customer_id`/`product_id` FKs, `net_revenue`, `profit`, `profit_margin_pct` |

`prepare_sql_csv.py` additionally writes `DimInventory_ForSql.csv` and
`FactSales_ForSql.csv` with the exact column order the SQL DDL expects, and
normalises `DimDate.csv` in place.

## DimRegion is at country grain

This is the single most important thing to know about the model.
`DimRegion` has one row per country, so `region_name` repeats — `R06` India,
`R07` Australia and `R08` Japan are all `Asia Pacific`.

**Any region-level aggregate must group on `region_name` alone.** Grouping on
`region_id`, or on `region_name` together with `country`, splits one region into
several apparent regions. `kpi_country_performance.csv` and `vw_CountryKPI`
provide the country grain as an explicit drill-down. See
`docs/KPI_DEFINITIONS.md`.

## Data quality rules applied by `clean_data.py`

- Duplicate `customer_id` / `order_id` rows dropped.
- Missing customer names filled with `"Unknown Customer"`; blank segments mapped
  to `"Unclassified"`.
- Customers with an invalid `region_id` reassigned to the `R00 — Unknown /
  Unassigned` region rather than dropped, preserving their revenue.
- Orders with non-positive `quantity` removed as data-entry errors.
- Missing `net_revenue` recomputed as `gross_amount - discount_amount`.
- `profit` and `profit_margin_pct` engineered from `net_revenue - total_cost`.

### The two data-quality buckets

`Unknown / Unassigned` (region) and `Unclassified` (segment) hold rows that
failed a check. They are **not business categories**. They appear in totals and
detail tables — dropping them would understate revenue — but the insights report
and any ranking exclude them, so a data-quality artefact is never returned as
"the worst-performing region" or "the segment to invest in". They carry 0.7% and
2.1% of revenue respectively.

## Known properties of the synthetic data

The generator assigns each order a customer and a product uniformly at random.
Two consequences show up in the reporting layer and are documented rather than
worked around:

- **Every customer is a repeat customer.** With 19,665 orders spread evenly over
  500 customers, each has ~39 orders, so `Repeat Customer Rate` reads 100% and
  carries no signal. Orders per customer is the useful depth measure here.
- **There is no revenue concentration.** The top 10 customers hold 3.1% of
  revenue, where a real B2B book would show a long Pareto tail.

Margins are also uniformly high (49.2% blended) because unit price is drawn as a
1.3×–2.6× markup on unit cost. Real category margin spread would be wider.

None of this affects the pipeline, the model or the KPI logic — it affects what
the numbers mean. Replacing `data/raw/` with a real extract restores normal
behaviour with no code changes.

## Swapping in your own data

Replace the files in `data/raw/` with the same column names, or point
`clean_data.py`'s `RAW_DIR` constant at your own extract, then re-run the
pipeline from `clean_data.py` onward (`generate_sample_data.py` is only needed
for the synthetic set).
