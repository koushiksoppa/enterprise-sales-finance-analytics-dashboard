/* ============================================================
   04_views.sql
   Reusable views for the Power BI / BI reporting layer.

   Power BI can import these instead of the processed CSVs; the column names
   match what powerbi/PowerQuery/power_query_m.pq produces, so the DAX
   measures work against either source.
   ============================================================ */

USE SalesAnalyticsDW;
GO

/* View: vw_SalesFlat - a fully denormalized, Power-BI-friendly flat table.
   The SQL mirror of build_sales_detail() in python/build_kpis.py. */
IF OBJECT_ID('dbo.vw_SalesFlat', 'V') IS NOT NULL DROP VIEW dbo.vw_SalesFlat;
GO
CREATE VIEW dbo.vw_SalesFlat AS
SELECT
    f.order_id,
    d.full_date,
    d.year,
    d.quarter,
    d.month,
    d.month_name,
    c.customer_id,
    c.customer_name,
    c.segment,
    r.region_name,
    r.country,
    p.product_id,
    p.product_name,
    p.category,
    f.quantity,
    f.unit_price,
    f.discount_pct,
    f.gross_amount,
    f.discount_amount,
    f.net_revenue,
    f.total_cost,
    f.profit,
    f.profit_margin_pct
FROM dbo.FactSales AS f
INNER JOIN dbo.DimDate     AS d ON f.date_id     = d.date_id
INNER JOIN dbo.DimCustomer AS c ON f.customer_id = c.customer_id
INNER JOIN dbo.DimRegion   AS r ON c.region_id   = r.region_id
INNER JOIN dbo.DimProduct  AS p ON f.product_id  = p.product_id;
GO

/* View: vw_RegionKPI - region grain for the Executive Dashboard.

   Grouped on region_name alone. DimRegion is at country grain, so including
   country here would split 'Asia Pacific' into three rows and every
   region-level visual built on this view would be wrong. Use
   vw_CountryKPI for the drill-down. */
IF OBJECT_ID('dbo.vw_RegionKPI', 'V') IS NOT NULL DROP VIEW dbo.vw_RegionKPI;
GO
CREATE VIEW dbo.vw_RegionKPI AS
SELECT
    r.region_name,
    COUNT(DISTINCT r.country)                                                   AS countries,
    SUM(f.net_revenue)                                                          AS total_revenue,
    SUM(f.profit)                                                               AS total_profit,
    COUNT(DISTINCT f.order_id)                                                  AS total_orders,
    COUNT(DISTINCT c.customer_id)                                               AS total_customers,
    CAST(SUM(f.net_revenue) / NULLIF(COUNT(DISTINCT f.order_id), 0)
         AS DECIMAL(12,2))                                                      AS avg_order_value,
    CAST(SUM(f.profit) * 100.0 / NULLIF(SUM(f.net_revenue), 0)
         AS DECIMAL(6,2))                                                       AS profit_margin_pct
FROM dbo.FactSales AS f
INNER JOIN dbo.DimCustomer AS c ON f.customer_id = c.customer_id
INNER JOIN dbo.DimRegion   AS r ON c.region_id   = r.region_id
GROUP BY r.region_name;
GO

/* View: vw_CountryKPI - country drill-down beneath vw_RegionKPI */
IF OBJECT_ID('dbo.vw_CountryKPI', 'V') IS NOT NULL DROP VIEW dbo.vw_CountryKPI;
GO
CREATE VIEW dbo.vw_CountryKPI AS
SELECT
    r.region_name,
    r.country,
    r.region_id,
    SUM(f.net_revenue)                                                          AS total_revenue,
    SUM(f.profit)                                                               AS total_profit,
    COUNT(DISTINCT f.order_id)                                                  AS total_orders,
    COUNT(DISTINCT c.customer_id)                                               AS total_customers,
    CAST(SUM(f.profit) * 100.0 / NULLIF(SUM(f.net_revenue), 0)
         AS DECIMAL(6,2))                                                       AS profit_margin_pct
FROM dbo.FactSales AS f
INNER JOIN dbo.DimCustomer AS c ON f.customer_id = c.customer_id
INNER JOIN dbo.DimRegion   AS r ON c.region_id   = r.region_id
GROUP BY r.region_name, r.country, r.region_id;
GO

/* View: vw_MonthlyKPI - the monthly trend series used by the Sales,
   Financial and Forecast pages, with MoM and YoY growth precomputed. */
IF OBJECT_ID('dbo.vw_MonthlyKPI', 'V') IS NOT NULL DROP VIEW dbo.vw_MonthlyKPI;
GO
CREATE VIEW dbo.vw_MonthlyKPI AS
WITH Monthly AS (
    SELECT
        d.year,
        d.month,
        MIN(d.full_date)            AS month_start,
        SUM(f.net_revenue)          AS revenue,
        SUM(f.profit)               AS profit,
        SUM(f.quantity)             AS units,
        COUNT(DISTINCT f.order_id)  AS orders,
        COUNT(DISTINCT f.customer_id) AS active_customers
    FROM dbo.FactSales AS f
    INNER JOIN dbo.DimDate AS d ON f.date_id = d.date_id
    GROUP BY d.year, d.month
)
SELECT
    year,
    month,
    month_start,
    revenue,
    profit,
    units,
    orders,
    active_customers,
    CAST(revenue / NULLIF(orders, 0) AS DECIMAL(12,2))                          AS avg_order_value,
    CAST(profit * 100.0 / NULLIF(revenue, 0) AS DECIMAL(6,2))                   AS profit_margin_pct,
    CAST((revenue - LAG(revenue, 1) OVER (ORDER BY year, month)) * 100.0
         / NULLIF(LAG(revenue, 1) OVER (ORDER BY year, month), 0)
         AS DECIMAL(8,2))                                                       AS mom_growth_pct,
    CAST((revenue - LAG(revenue, 12) OVER (ORDER BY year, month)) * 100.0
         / NULLIF(LAG(revenue, 12) OVER (ORDER BY year, month), 0)
         AS DECIMAL(8,2))                                                       AS yoy_growth_pct
FROM Monthly;
GO

/* View: vw_InventoryRisk - reorder risk for the Inventory Analytics page.
   risk_flag uses the same two thresholds as inventory_turnover() in
   python/build_kpis.py, so a product flagged there is flagged here. */
IF OBJECT_ID('dbo.vw_InventoryRisk', 'V') IS NOT NULL DROP VIEW dbo.vw_InventoryRisk;
GO
CREATE VIEW dbo.vw_InventoryRisk AS
SELECT
    p.product_id,
    p.product_name,
    p.category,
    i.warehouse,
    i.stock_quantity,
    i.reorder_level,
    i.stock_quantity - i.reorder_level                                          AS stock_vs_reorder,
    CAST(i.stock_quantity * p.unit_cost AS DECIMAL(14,2))                       AS stock_value,
    i.needs_reorder,
    COALESCE(s.units_sold, 0)                                                   AS units_sold,
    CAST(COALESCE(s.units_sold, 0) * 1.0 / NULLIF(i.stock_quantity, 0)
         AS DECIMAL(10,2))                                                      AS turnover_ratio,
    CASE
        WHEN i.stock_quantity <= i.reorder_level        THEN 'REORDER NOW'
        WHEN i.stock_quantity <= i.reorder_level * 1.25 THEN 'AT RISK'
        ELSE 'OK'
    END                                                                         AS risk_flag
FROM dbo.DimInventory AS i
INNER JOIN dbo.DimProduct AS p ON i.product_id = p.product_id
LEFT JOIN (
    SELECT product_id, SUM(quantity) AS units_sold
    FROM dbo.FactSales
    GROUP BY product_id
) AS s ON p.product_id = s.product_id;
GO

/* View: vw_ProductKPI - product grain with the shared margin bands applied */
IF OBJECT_ID('dbo.vw_ProductKPI', 'V') IS NOT NULL DROP VIEW dbo.vw_ProductKPI;
GO
CREATE VIEW dbo.vw_ProductKPI AS
SELECT
    p.product_id,
    p.product_name,
    p.category,
    SUM(f.net_revenue)                                                          AS total_revenue,
    SUM(f.profit)                                                               AS total_profit,
    SUM(f.quantity)                                                             AS units_sold,
    COUNT(DISTINCT f.order_id)                                                  AS total_orders,
    CAST(SUM(f.profit) * 100.0 / NULLIF(SUM(f.net_revenue), 0)
         AS DECIMAL(6,2))                                                       AS profit_margin_pct,
    CASE
        WHEN SUM(f.profit) * 1.0 / NULLIF(SUM(f.net_revenue), 0) >= 0.35 THEN 'Healthy'
        WHEN SUM(f.profit) * 1.0 / NULLIF(SUM(f.net_revenue), 0) >= 0.20 THEN 'Watch'
        ELSE 'At Risk'
    END                                                                         AS margin_status
FROM dbo.DimProduct AS p
INNER JOIN dbo.FactSales AS f ON p.product_id = f.product_id
GROUP BY p.product_id, p.product_name, p.category;
GO
