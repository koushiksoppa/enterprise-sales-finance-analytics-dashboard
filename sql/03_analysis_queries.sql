/* ============================================================
   03_analysis_queries.sql
   Business KPI & analytical queries against the star schema.
   Target: Microsoft SQL Server 2019+

   These queries are the T-SQL mirror of python/build_kpis.py and of the DAX
   measures in powerbi/DAX/measures.dax. Where the three could drift, the
   definition is written once in docs/KPI_DEFINITIONS.md and implemented the
   same way in each layer. Running these against a freshly loaded warehouse
   should reproduce the numbers in reports/*.csv exactly.
   ============================================================ */

USE SalesAnalyticsDW;
GO

/* ------------------------------------------------------------
   1. Revenue, Profit and Margin by REGION  (INNER JOIN + GROUP BY)

   DimRegion is at country grain, so region_name repeats across region_ids
   (three rows are 'Asia Pacific'). Grouping by region_id - or by
   region_name together with country - splits one region into several
   apparent regions. Region-level KPIs must group on region_name alone;
   query 1b below is the country-level drill-down.
   ------------------------------------------------------------ */
SELECT
    r.region_name,
    COUNT(DISTINCT r.country)                                                    AS countries,
    COUNT(DISTINCT f.order_id)                                                   AS total_orders,
    COUNT(DISTINCT f.customer_id)                                                AS total_customers,
    SUM(f.net_revenue)                                                           AS total_revenue,
    SUM(f.profit)                                                                AS total_profit,
    CAST(SUM(f.net_revenue) / NULLIF(COUNT(DISTINCT f.order_id), 0)
         AS DECIMAL(12,2))                                                       AS avg_order_value,
    CAST(SUM(f.profit) * 100.0 / NULLIF(SUM(f.net_revenue), 0)
         AS DECIMAL(6,2))                                                        AS profit_margin_pct,
    CAST(SUM(f.net_revenue) * 100.0 / NULLIF(SUM(SUM(f.net_revenue)) OVER (), 0)
         AS DECIMAL(6,2))                                                        AS revenue_share_pct
FROM dbo.FactSales AS f
INNER JOIN dbo.DimCustomer AS c ON f.customer_id = c.customer_id
INNER JOIN dbo.DimRegion   AS r ON c.region_id   = r.region_id
GROUP BY r.region_name
ORDER BY total_revenue DESC;
GO

/* ------------------------------------------------------------
   1b. Country drill-down beneath the region rollup
   ------------------------------------------------------------ */
SELECT
    r.region_name,
    r.country,
    r.region_id,
    COUNT(DISTINCT f.order_id)                                                   AS total_orders,
    SUM(f.net_revenue)                                                           AS total_revenue,
    SUM(f.profit)                                                                AS total_profit,
    CAST(SUM(f.profit) * 100.0 / NULLIF(SUM(f.net_revenue), 0)
         AS DECIMAL(6,2))                                                        AS profit_margin_pct
FROM dbo.FactSales AS f
INNER JOIN dbo.DimCustomer AS c ON f.customer_id = c.customer_id
INNER JOIN dbo.DimRegion   AS r ON c.region_id   = r.region_id
GROUP BY r.region_name, r.country, r.region_id
ORDER BY total_revenue DESC;
GO

/* ------------------------------------------------------------
   2. Products earning below the portfolio margin
      (LEFT JOIN + GROUP BY + HAVING + scalar subquery)

   Both sides of the comparison are revenue-weighted margins. Comparing a
   product's weighted margin against AVG(profit_margin_pct) over the fact
   rows would compare a weighted figure with an unweighted one and
   misclassify products whose cheap lines outnumber their expensive ones.
   ------------------------------------------------------------ */
DECLARE @PortfolioMargin DECIMAL(9,6) = (
    SELECT SUM(profit) * 1.0 / NULLIF(SUM(net_revenue), 0) FROM dbo.FactSales
);

SELECT
    p.product_id,
    p.product_name,
    p.category,
    SUM(f.net_revenue)                                                           AS total_revenue,
    SUM(f.profit)                                                                AS total_profit,
    CAST(SUM(f.profit) * 100.0 / NULLIF(SUM(f.net_revenue), 0)
         AS DECIMAL(6,2))                                                        AS margin_pct,
    CAST(@PortfolioMargin * 100 AS DECIMAL(6,2))                                 AS portfolio_margin_pct,
    CASE
        WHEN SUM(f.profit) * 1.0 / NULLIF(SUM(f.net_revenue), 0) >= 0.35 THEN 'Healthy'
        WHEN SUM(f.profit) * 1.0 / NULLIF(SUM(f.net_revenue), 0) >= 0.20 THEN 'Watch'
        ELSE 'At Risk'
    END                                                                          AS margin_status
FROM dbo.DimProduct AS p
LEFT JOIN dbo.FactSales AS f ON p.product_id = f.product_id
GROUP BY p.product_id, p.product_name, p.category
HAVING SUM(f.net_revenue) > 0
   AND SUM(f.profit) * 1.0 / NULLIF(SUM(f.net_revenue), 0) < @PortfolioMargin
ORDER BY margin_pct ASC;
GO

/* ------------------------------------------------------------
   3. Monthly Revenue Trend with Running Total, MoM and YoY Growth
      (Window Functions: SUM OVER, LAG)
   ------------------------------------------------------------ */
WITH MonthlyRevenue AS (
    SELECT
        d.year,
        d.month,
        d.month_name,
        SUM(f.net_revenue)              AS monthly_revenue,
        SUM(f.profit)                   AS monthly_profit,
        COUNT(DISTINCT f.order_id)      AS monthly_orders
    FROM dbo.FactSales AS f
    INNER JOIN dbo.DimDate AS d ON f.date_id = d.date_id
    GROUP BY d.year, d.month, d.month_name
)
SELECT
    year,
    month,
    month_name,
    monthly_revenue,
    monthly_profit,
    CAST(monthly_revenue / NULLIF(monthly_orders, 0) AS DECIMAL(12,2))           AS avg_order_value,
    CAST(monthly_profit * 100.0 / NULLIF(monthly_revenue, 0) AS DECIMAL(6,2))    AS profit_margin_pct,
    SUM(monthly_revenue) OVER (ORDER BY year, month
                               ROWS UNBOUNDED PRECEDING)                         AS running_total_revenue,
    CAST((monthly_revenue - LAG(monthly_revenue, 1) OVER (ORDER BY year, month))
         * 100.0 / NULLIF(LAG(monthly_revenue, 1) OVER (ORDER BY year, month), 0)
         AS DECIMAL(6,2))                                                        AS mom_growth_pct,
    -- 12 rows back is the same calendar month a year earlier, because the
    -- series has one row per month with no gaps.
    CAST((monthly_revenue - LAG(monthly_revenue, 12) OVER (ORDER BY year, month))
         * 100.0 / NULLIF(LAG(monthly_revenue, 12) OVER (ORDER BY year, month), 0)
         AS DECIMAL(6,2))                                                        AS yoy_growth_pct
FROM MonthlyRevenue
ORDER BY year, month;
GO

/* ------------------------------------------------------------
   4. Top 5 Customers per Region  (Window Function: RANK)
   ------------------------------------------------------------ */
WITH CustomerRevenue AS (
    SELECT
        r.region_name,
        c.customer_id,
        c.customer_name,
        c.segment,
        SUM(f.net_revenue) AS total_revenue,
        COUNT(DISTINCT f.order_id) AS total_orders,
        RANK() OVER (PARTITION BY r.region_name ORDER BY SUM(f.net_revenue) DESC) AS revenue_rank
    FROM dbo.FactSales AS f
    INNER JOIN dbo.DimCustomer AS c ON f.customer_id = c.customer_id
    INNER JOIN dbo.DimRegion   AS r ON c.region_id   = r.region_id
    GROUP BY r.region_name, c.customer_id, c.customer_name, c.segment
)
SELECT *
FROM CustomerRevenue
WHERE revenue_rank <= 5
ORDER BY region_name, revenue_rank;
GO

/* ------------------------------------------------------------
   5. Customer Growth by Signup Month (CTE)

   Signups are an acquisition measure and start before the sales window, so
   this series deliberately does not align with the monthly revenue series
   above. Query 5b counts customers who actually transacted in each month.
   ------------------------------------------------------------ */
WITH SignupsByMonth AS (
    SELECT
        FORMAT(signup_date, 'yyyy-MM') AS signup_month,
        COUNT(*) AS new_customers
    FROM dbo.DimCustomer
    GROUP BY FORMAT(signup_date, 'yyyy-MM')
)
SELECT
    signup_month,
    new_customers,
    SUM(new_customers) OVER (ORDER BY signup_month ROWS UNBOUNDED PRECEDING) AS cumulative_customers
FROM SignupsByMonth
ORDER BY signup_month;
GO

/* 5b. Active (transacting) customers per month */
SELECT
    d.year,
    d.month,
    COUNT(DISTINCT f.customer_id) AS active_customers
FROM dbo.FactSales AS f
INNER JOIN dbo.DimDate AS d ON f.date_id = d.date_id
GROUP BY d.year, d.month
ORDER BY d.year, d.month;
GO

/* ------------------------------------------------------------
   5c. Repeat Customer Rate  (customers with more than one order)
   ------------------------------------------------------------ */
WITH OrdersPerCustomer AS (
    SELECT customer_id, COUNT(DISTINCT order_id) AS order_count
    FROM dbo.FactSales
    GROUP BY customer_id
)
SELECT
    COUNT(*)                                                                     AS transacting_customers,
    SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END)                             AS repeat_customers,
    CAST(SUM(CASE WHEN order_count > 1 THEN 1.0 ELSE 0 END) * 100.0 / COUNT(*)
         AS DECIMAL(6,2))                                                        AS repeat_customer_rate_pct,
    CAST(AVG(order_count * 1.0) AS DECIMAL(8,2))                                 AS avg_orders_per_customer
FROM OrdersPerCustomer;
GO

/* ------------------------------------------------------------
   6. Inventory Turnover & Reorder Risk (LEFT JOIN + CASE)

   Units sold covers the whole reporting period while stock_quantity is a
   point-in-time snapshot, so turnover_ratio ranks relative velocity between
   products rather than reporting an annualised turn rate.
   ------------------------------------------------------------ */
SELECT
    p.product_id,
    p.product_name,
    p.category,
    i.warehouse,
    i.stock_quantity,
    i.reorder_level,
    i.stock_quantity - i.reorder_level                                           AS stock_vs_reorder,
    CAST(i.stock_quantity * p.unit_cost AS DECIMAL(14,2))                        AS stock_value,
    COALESCE(SUM(f.quantity), 0)                                                 AS units_sold,
    CAST(COALESCE(SUM(f.quantity), 0) * 1.0 / NULLIF(i.stock_quantity, 0)
         AS DECIMAL(10,2))                                                       AS turnover_ratio,
    CASE
        WHEN i.stock_quantity <= i.reorder_level             THEN 'REORDER NOW'
        WHEN i.stock_quantity <= i.reorder_level * 1.25      THEN 'AT RISK'
        ELSE 'OK'
    END                                                                          AS risk_flag
FROM dbo.DimInventory AS i
INNER JOIN dbo.DimProduct AS p ON i.product_id = p.product_id
LEFT JOIN dbo.FactSales AS f ON p.product_id = f.product_id
GROUP BY p.product_id, p.product_name, p.category, i.warehouse,
         i.stock_quantity, i.reorder_level, p.unit_cost
ORDER BY turnover_ratio DESC;
GO

/* ------------------------------------------------------------
   7. Average Order Value & Revenue by Quarter
   ------------------------------------------------------------ */
SELECT
    d.year,
    d.quarter,
    COUNT(DISTINCT f.order_id)                                                   AS total_orders,
    SUM(f.net_revenue)                                                           AS total_revenue,
    CAST(SUM(f.net_revenue) * 1.0 / COUNT(DISTINCT f.order_id)
         AS DECIMAL(12,2))                                                       AS avg_order_value
FROM dbo.FactSales AS f
INNER JOIN dbo.DimDate AS d ON f.date_id = d.date_id
GROUP BY d.year, d.quarter
ORDER BY d.year, d.quarter;
GO

/* ------------------------------------------------------------
   8. Category performance (Sales & Financial Analytics pages)
   ------------------------------------------------------------ */
SELECT
    p.category,
    COUNT(DISTINCT p.product_id)                                                 AS products,
    COUNT(DISTINCT f.order_id)                                                   AS total_orders,
    SUM(f.quantity)                                                              AS units_sold,
    SUM(f.net_revenue)                                                           AS total_revenue,
    SUM(f.profit)                                                                AS total_profit,
    CAST(SUM(f.net_revenue) / NULLIF(COUNT(DISTINCT f.order_id), 0)
         AS DECIMAL(12,2))                                                       AS avg_order_value,
    CAST(SUM(f.profit) * 100.0 / NULLIF(SUM(f.net_revenue), 0)
         AS DECIMAL(6,2))                                                        AS profit_margin_pct,
    CAST(SUM(f.net_revenue) * 100.0 / NULLIF(SUM(SUM(f.net_revenue)) OVER (), 0)
         AS DECIMAL(6,2))                                                        AS revenue_share_pct
FROM dbo.FactSales AS f
INNER JOIN dbo.DimProduct AS p ON f.product_id = p.product_id
GROUP BY p.category
ORDER BY total_revenue DESC;
GO

/* ------------------------------------------------------------
   9. Customer segment performance (Customer Analytics page)

   'Unclassified' is the bucket for customers whose source segment arrived
   blank. It is reported, but excluded from segment rankings elsewhere.
   ------------------------------------------------------------ */
WITH SegmentOrders AS (
    SELECT c.segment, f.customer_id, COUNT(DISTINCT f.order_id) AS order_count
    FROM dbo.FactSales AS f
    INNER JOIN dbo.DimCustomer AS c ON f.customer_id = c.customer_id
    GROUP BY c.segment, f.customer_id
)
SELECT
    c.segment,
    COUNT(DISTINCT f.customer_id)                                                AS total_customers,
    COUNT(DISTINCT f.order_id)                                                   AS total_orders,
    SUM(f.net_revenue)                                                           AS total_revenue,
    SUM(f.profit)                                                                AS total_profit,
    CAST(SUM(f.net_revenue) / NULLIF(COUNT(DISTINCT f.customer_id), 0)
         AS DECIMAL(14,2))                                                       AS revenue_per_customer,
    CAST(SUM(f.profit) * 100.0 / NULLIF(SUM(f.net_revenue), 0)
         AS DECIMAL(6,2))                                                        AS profit_margin_pct,
    (SELECT CAST(SUM(CASE WHEN s.order_count > 1 THEN 1.0 ELSE 0 END) * 100.0
                 / NULLIF(COUNT(*), 0) AS DECIMAL(6,2))
     FROM SegmentOrders AS s WHERE s.segment = c.segment)                        AS repeat_customer_rate_pct
FROM dbo.FactSales AS f
INNER JOIN dbo.DimCustomer AS c ON f.customer_id = c.customer_id
GROUP BY c.segment
ORDER BY total_revenue DESC;
GO
