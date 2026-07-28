/* ============================================================
   04_views.sql
   Reusable views for Power BI / BI reporting layer.
   ============================================================ */

USE SalesAnalyticsDW;
GO

/* View: vw_SalesFlat — a fully denormalized, Power-BI-friendly flat table */
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

/* View: vw_RegionalKPI — pre-aggregated regional KPI for the Executive Dashboard */
IF OBJECT_ID('dbo.vw_RegionalKPI', 'V') IS NOT NULL DROP VIEW dbo.vw_RegionalKPI;
GO
CREATE VIEW dbo.vw_RegionalKPI AS
SELECT
    r.region_name,
    r.country,
    SUM(f.net_revenue)                                                              AS total_revenue,
    SUM(f.profit)                                                                   AS total_profit,
    COUNT(DISTINCT f.order_id)                                                      AS total_orders,
    COUNT(DISTINCT c.customer_id)                                                   AS total_customers,
    CAST(SUM(f.profit) * 100.0 / NULLIF(SUM(f.net_revenue), 0) AS DECIMAL(6,2))     AS profit_margin_pct
FROM dbo.FactSales AS f
INNER JOIN dbo.DimCustomer AS c ON f.customer_id = c.customer_id
INNER JOIN dbo.DimRegion   AS r ON c.region_id   = r.region_id
GROUP BY r.region_name, r.country;
GO

/* View: vw_InventoryRisk — reorder risk for the Inventory Analytics page */
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
    i.needs_reorder,
    COALESCE(s.units_sold, 0) AS units_sold
FROM dbo.DimInventory AS i
INNER JOIN dbo.DimProduct AS p ON i.product_id = p.product_id
LEFT JOIN (
    SELECT product_id, SUM(quantity) AS units_sold
    FROM dbo.FactSales
    GROUP BY product_id
) AS s ON p.product_id = s.product_id;
GO
