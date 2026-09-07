# Executive Business Review

**Sales, profitability, customer and inventory performance**  
Reporting period: Jan 2022 to Dec 2024 (36 months) · Generated 2026-09-07

> Figures are computed directly from the KPI tables in `reports/` by `python/build_kpis.py`. Definitions for every metric are in `docs/KPI_DEFINITIONS.md`.

## Performance at a glance

| Metric | Value |
|---|---|
| Total Revenue | $103,116,815 |
| Total Profit | $50,733,132 |
| Profit Margin % | 49.2% |
| Revenue Growth YoY % | +7.0% |
| Total Orders | 19,665 |
| Average Order Value | $5,244 |
| Total Customers | 500 |
| Repeat Customer Rate % | 100.0% |

## Where the business is growing

- **Strongest region:** Asia Pacific — $34,805,424 revenue (33.8% of the total) at 49.1% margin, across 3 countries.
- **Weakest region by revenue:** Latin America — $20,265,923 (19.6% of the total) at 49.1% margin.
- **Margin spread across regions** is narrow: 49.1% (Asia Pacific) to 49.4% (Europe), so revenue mix — not regional pricing — drives the profit differences.
- **Largest category:** Electronics — $23,535,063 (22.8% of revenue) at 53.6% margin.

## Profitability

- **Highest revenue product:** Mechanical Keyboard (Electronics) — $10,574,742 revenue, 58.8% margin.
- **Highest profit product:** Mechanical Keyboard (Electronics) — $6,215,427 profit.
- **Lowest margin product:** Ergo Office Chair (Office Supplies) at 22.4% — status *Watch* against the 35.0% / 20.0% margin bands.
- **Weakest category by margin:** Office Supplies at 43.6%.

## Customers

- 500 customers placed at least one order; 500 are on file in total.
- **Repeat customer rate:** 100.0% of transacting customers ordered more than once, so the metric is saturated on this customer base and carries no signal - average orders per customer is the more informative depth measure here.
- **Orders per customer:** 39.3 on average across the period.
- **Revenue concentration:** the top 10 customers hold 3.1% of total revenue - revenue is broadly distributed, so no single account is a material dependency.
- **Largest segment:** SMB — $34,066,071 (33.0% of revenue) from 166 customers, $205,217 each.
- Acquisition is measured from customer signup dates, which run 2021-01 to 2024-10 — a wider window than the sales period.

## Inventory risk

- **Stock on hand:** $2,587,060 at cost across 22 product/warehouse positions.
- **Inventory turnover:** 21.03x — units sold over the full 36-month period against a point-in-time stock snapshot, so it measures relative velocity between products rather than an annualised turn rate.
- **At or below reorder level:** 1 product(s).
  - Lounge Sofa (P0017) in WH-WEST — stock 27 vs reorder level 27
- **Within 25% of the reorder trigger:** 1 product(s).

## Outlook

- A seasonal linear-trend model projects $17,783,698 of revenue for Jan 2025 to Jun 2025, within a modelled range of $15,238,026 to $20,329,370.
- That is +8.8% against the same months a year earlier (Jan 2024 to Jun 2024: $16,338,681). The comparison is year-on-year rather than against the trailing six months, which end on the November/December peak and would read a normal seasonal step-down as decline.
- The projection extrapolates the observed trend and month-of-year seasonality. It is a planning input, not a commitment, and it assumes no change in pricing, product mix, or market conditions.

## Recommendations

1. Address the margin gap in Office Supplies: 43.6% margin on $17.8M of revenue, 5.6 points below the 49.2% blended margin. It is the weakest category and the largest structural drag on portfolio profitability.
2. Reprice or renegotiate supply for Ergo Office Chair (22.4% margin). It carries $4.7M of revenue, so a margin correction here moves the portfolio, not just the line item.
3. Fund coverage in Asia Pacific, which already contributes 33.8% of revenue at 49.1% margin, and run a commercial review in Latin America (19.6% share).
4. Raise replenishment orders for 1 product(s) now at or below the reorder trigger (Lounge Sofa) before the next order cycle converts the shortfall into lost revenue.
5. Retention is not the constraint - 100.0% of customers already reorder, the top 10 accounts hold only 3.1% of revenue, and revenue per customer varies by just 6% across segments. The material lever is product mix, not customer mix: Software carries a $6,579 average order against $3,950 in Office Supplies, and Electronics is the highest-margin category at 53.6%.

## Data quality note

- $714,040 of revenue (0.7%, 147 orders) belongs to customers whose source `region_id` failed referential integrity. The ETL preserves the revenue in an *Unknown / Unassigned* bucket rather than dropping it, and regional rankings above exclude the bucket so a data-quality artefact is never reported as a market finding.
- 10 customers (2.1% of revenue) arrived with a blank segment and sit in an *Unclassified* bucket. They appear in the segment table but are excluded from segment rankings for the same reason.
- Region rankings roll countries up to their region. `DimRegion` is at country grain, so grouping by `region_id` would split one region into several.
