# Dataset Description

The sample dataset is synthetically generated (`python/generate_sample_data.py`,
seeded for reproducibility) to resemble a mid-size B2B/B2C hardware &
software retailer operating across 4 global regions. It is deliberately
"messy" — duplicate rows, missing values, and invalid quantities — so the
cleaning pipeline demonstrates real data-engineering work rather than
operating on already-perfect data.

## Raw tables (`data/raw/`)

| File | Rows (approx.) | Description |
|---|---|---|
| `regions.csv` | 11 | Region/country reference |
| `customers.csv` | ~510 | Customer master, with ~2% duplicate rows, ~3% missing names |
| `products.csv` | 22 | Product catalog across 5 categories |
| `inventory.csv` | 22 | Stock levels per product per warehouse |
| `sales_transactions.csv` | ~20,200 | Order-line grain sales, 2022–2024, with ~1.5% invalid quantities and ~1% missing revenue |

## Processed star schema (`data/processed/`)

| Table | Grain | Key columns |
|---|---|---|
| `DimDate` | 1 row per day | `date_id` (YYYYMMDD int PK), calendar attributes, `fiscal_year` |
| `DimCustomer` | 1 row per customer | `customer_id` PK, `segment`, `region_id` FK, `signup_date` |
| `DimProduct` | 1 row per product | `product_id` PK, `category`, `unit_cost`, `unit_price`, `margin_pct` |
| `DimRegion` | 1 row per region | `region_id` PK, `region_name`, `country` |
| `DimInventory` | 1 row per product/warehouse | `product_id` FK, `stock_quantity`, `reorder_level`, `needs_reorder` |
| `FactSales` | 1 row per order line | `order_id` PK, `date_id`/`customer_id`/`product_id` FKs, `net_revenue`, `profit`, `profit_margin_pct` |

## Data quality rules applied by `clean_data.py`
- Duplicate `customer_id` / `order_id` rows dropped.
- Missing customer names filled with `"Unknown Customer"`; blank segments
  mapped to `"Unclassified"`.
- Customers with an invalid `region_id` reassigned to the `R00 — Unknown /
  Unassigned` region rather than dropped, preserving revenue.
- Orders with non-positive `quantity` removed (data-entry errors).
- Missing `net_revenue` recomputed from `gross_amount - discount_amount`.
- `profit` and `profit_margin_pct` engineered from `net_revenue - total_cost`.

## Swapping in your own data
Replace the files in `data/raw/` with the same column names, or point
`clean_data.py`'s `RAW_DIR` constant at your own extract, then re-run the
pipeline (`generate_sample_data.py` is optional once you have real data).
