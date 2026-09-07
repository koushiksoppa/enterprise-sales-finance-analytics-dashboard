# KPI Definitions

The same KPI is computed in three places — Python (`python/build_kpis.py`),
T-SQL (`sql/03_analysis_queries.sql`, `sql/04_views.sql`) and DAX
(`powerbi/DAX/measures.dax`). This file is the contract between them. Change a
definition here first, then in all three layers.

Every figure in `reports/` and in the dashboard previews comes from these
definitions. Running the SQL against a freshly loaded warehouse should
reproduce the Python numbers exactly.

## Conventions

| Convention | Rule |
|---|---|
| Revenue | `net_revenue` — gross amount less discount. Never gross. |
| Profit | `net_revenue - total_cost`. Direct product cost only; no overhead. |
| Margin | **Revenue-weighted**: `SUM(profit) / SUM(net_revenue)`. Never the mean of row-level margins. |
| Order grain | One row per `order_id` in `FactSales`; order lines and orders are the same grain in this dataset. |
| Region grain | `DimRegion[region_name]`. See [Region vs country](#region-vs-country). |
| Currency | Unscaled USD in the data; abbreviated only for display. |

## Core KPIs

### Revenue

Sum of net revenue across all order lines in the filter context.

| Layer | Implementation |
|---|---|
| Python | `detail["net_revenue"].sum()` |
| T-SQL | `SUM(f.net_revenue)` |
| DAX | `Total Revenue = SUM ( FactSales[net_revenue] )` |

### Profit

Net revenue less total cost.

| Layer | Implementation |
|---|---|
| Python | `detail["profit"].sum()` |
| T-SQL | `SUM(f.profit)` |
| DAX | `Total Profit = SUM ( FactSales[profit] )` |

### Profit Margin %

Total profit divided by total revenue, expressed as a percentage.

| Layer | Implementation |
|---|---|
| Python | `_margin_pct(profit, revenue)` |
| T-SQL | `SUM(f.profit) * 100.0 / NULLIF(SUM(f.net_revenue), 0)` |
| DAX | `Profit Margin % = DIVIDE ( [Total Profit], [Total Revenue], 0 )` |

Revenue-weighted by design. Averaging `FactSales[profit_margin_pct]` across
rows would weight a $40 order the same as a $40,000 one and would not tie back
to Revenue and Profit.

### Sales Growth MoM / YoY

Month-over-month is the change against the previous calendar month.
Year-over-year is the change against the same month one year earlier — 12 rows
back on a gap-free monthly series, or `SAMEPERIODLASTYEAR` in DAX.

| Layer | Implementation |
|---|---|
| Python | `monthly["revenue"].pct_change()` and `.pct_change(periods=12)` |
| T-SQL | `LAG(monthly_revenue, 1)` and `LAG(monthly_revenue, 12)` over `(ORDER BY year, month)` |
| DAX | `Sales Growth MoM %`, `Revenue YoY %` |

The headline `Revenue Growth YoY %` in `kpi_executive_summary.csv` compares
**full calendar years** (2024 vs 2023), not the last month against its
counterpart. Both are legitimate; the report states which it is using.

### Average Order Value

Total revenue divided by distinct orders.

| Layer | Implementation |
|---|---|
| Python | `revenue / orders` |
| T-SQL | `SUM(f.net_revenue) / COUNT(DISTINCT f.order_id)` |
| DAX | `Average Order Value = DIVIDE ( [Total Revenue], [Total Orders], 0 )` |

### Customer Growth %

Change in distinct transacting customers against the same period a year
earlier. Distinct from **new customers**, which counts signups.

| Layer | Implementation |
|---|---|
| Python | `customer_growth()` — cumulative customers on file, month over month |
| T-SQL | Query 5 (signups) and 5b (active customers) |
| DAX | `Customer Growth %`, `New Customers` (via the inactive signup-date relationship) |

Signup dates run from 2021-01, before the sales window opens in 2022-01, so
the acquisition series and the demand series deliberately do not align.

### Repeat Customer Rate

Customers with more than one order, divided by all customers with at least one.

| Layer | Implementation |
|---|---|
| Python | `orders_per_customer.gt(1).mean()` |
| T-SQL | Query 5c |
| DAX | `Repeat Customer Rate` |

**Read with care on the shipped dataset.** The generator assigns orders to
customers uniformly at random across ~19,700 orders and 500 customers, so every
customer has ordered many times and this metric reads 100%. It is reported
truthfully rather than adjusted, and `Orders Per Customer` (39.3) is the
informative depth measure. On a real transactional extract the metric behaves
normally.

### Inventory Turnover Ratio

Units sold divided by units on hand.

| Layer | Implementation |
|---|---|
| Python | `units_sold / stock_quantity` per product; `inventory_turnover()` |
| T-SQL | Query 6, `vw_InventoryRisk` |
| DAX | `Inventory Turnover Ratio = DIVIDE ( [Total Units Sold], [Total Stock On Hand], 0 )` |

Units sold spans the full 36-month period while stock is a point-in-time
snapshot, so the ratio ranks relative velocity between products. It is not an
annualised turn rate and should not be read as one.

### Top Products / Top Customers

Ranked by revenue descending, with profit, units and margin alongside so a
high-revenue, low-margin line is visible rather than hidden.

| Layer | Implementation |
|---|---|
| Python | `top_products()`, `top_customers()` |
| T-SQL | Query 4, `vw_ProductKPI` |
| DAX | `Product Revenue Rank`, `Customer Revenue Rank` (`RANKX` over `ALLSELECTED`) |

### Regional Performance

Revenue, profit, margin, orders, customers and revenue share at region grain.

| Layer | Implementation |
|---|---|
| Python | `regional_performance()` |
| T-SQL | Query 1, `vw_RegionKPI` |
| DAX | Group visuals on `DimRegion[region_name]`; `Region Revenue Rank` |

## Region vs country

`DimRegion` has one row per **country** (`R01` USA, `R02` Canada, …), so
`region_name` repeats: three rows are `Asia Pacific`. Any region-level
aggregate must group on `region_name` alone.

Grouping on `region_id` — or on `region_name, country` — splits one region into
several apparent regions. That was a real defect in this repository: the
generated `kpi_regional_performance.csv` listed "Asia Pacific" three times, and
the insights report named the largest of the three fragments ($14.2M) as the
best-performing region when the region actually earns $34.8M. Country detail
now lives in `kpi_country_performance.csv` / `vw_CountryKPI`.

## Data-quality buckets

Two dimension values are not business categories. They hold rows that failed a
data-quality check and are preserved so revenue is never silently dropped:

| Bucket | Meaning | Handling |
|---|---|---|
| `Unknown / Unassigned` region (`R00`) | Customer's source `region_id` failed referential integrity | Shown in detail tables and totals; **excluded from regional rankings** and from best/worst findings |
| `Unclassified` segment | Customer's source segment arrived blank | Shown in the segment table; **excluded from segment rankings** |

Together they carry 0.7% and 2.1% of revenue respectively. The insights report
states both figures under "Data quality" rather than burying them.

## Margin health bands

One set of thresholds, applied identically in all three layers:

| Band | Realised margin | Colour |
|---|---|---|
| Healthy | ≥ 35% | `#1F7A54` |
| Watch | 20% – 35% | `#B0791C` |
| At Risk | < 20% | `#A93226` |

| Layer | Implementation |
|---|---|
| Python | `report_theme.margin_status()` |
| T-SQL | `CASE` in query 2 and `vw_ProductKPI` |
| DAX | `Margin Status`, `Margin Status Colour` |

`DimProduct[Margin Band]` is a different thing: it bands the **catalogue**
margin from list price and cost, before discounting. The Financial Analytics
page reports realised margin.

## Reorder risk bands

| Flag | Condition |
|---|---|
| `REORDER NOW` | `stock_quantity <= reorder_level` |
| `AT RISK` | `stock_quantity <= reorder_level * 1.25` |
| `OK` | otherwise |

| Layer | Implementation |
|---|---|
| Python | `inventory_turnover()` |
| T-SQL | Query 6, `vw_InventoryRisk` |
| DAX | `Products Needing Reorder`, `Products At Risk`, `DimInventory[Risk Flag]` |

## Forecast

`kpi_revenue_forecast.csv` and the Forecast Dashboard page project six months
beyond the last actual month.

**Method.** Ordinary least squares of monthly revenue on a continuous month
index gives the trend. That trend is multiplied by a month-of-year seasonal
index — the mean ratio of actual to trend for each calendar month, normalised
to average 1 — which is what carries the November/December peak forward. The
band is the projection ± 1.96 residual standard deviations of the in-sample
fit.

**What it is not.** The band describes historical dispersion around the fit,
not a probability that future revenue lands inside it. The projection assumes
pricing, product mix and market conditions hold. Every surface that shows it
labels it as modelled and separates it visually from recorded actuals.

| Layer | Implementation |
|---|---|
| Python | `revenue_forecast()` |
| DAX | `Revenue Trend Slope`, `Revenue Trend Intercept`, `Linear Trend Revenue`, `Revenue 3M Moving Avg` |
| Power BI | Analytics pane → Forecast on the revenue line chart |

The DAX trend regresses against `DimDate[Month Index]`, a monotonic month
counter. Regressing against `DimDate[month]` (1–12) fits the shape of a
calendar year rather than the trend across the series — that was the previous
implementation and it produced a meaningless projection.

## Comparison baselines

When the Outlook section compares the projection with history it uses the
**same calendar months a year earlier**, not the trailing six months. The
trailing window ends on the November/December peak, so a trailing comparison
reports a normal seasonal step-down as a decline. The like-for-like comparison
(Jan–Jun 2025 vs Jan–Jun 2024) is +8.8%; the trailing comparison would have
read −7.1% from the same forecast.
