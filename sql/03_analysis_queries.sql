/* ============================================================
   03_analysis_queries.sql
   Business KPI & analytical queries against the star schema.
   Target: Microsoft SQL Server 2019+
   ============================================================ */

USE SalesAnalyticsDW;
GO

/* ------------------------------------------------------------
   1. Revenue, Profit, Margin by Region  (INNER JOIN + GROUP BY)
   ------------------------------------------------------------ */
SELECT
    r.region_name,
    r.country,
    COUNT(DISTINCT f.order_id)              AS total_orders,
    SUM(f.net_revenue)                      AS total_revenue,
    SUM(f.profit)                           AS total_profit,
    CAST(SUM(f.profit) * 100.0 / NULLIF(SUM(f.net_revenue), 0) AS DECIMAL(6,2)) AS profit_margin_pct
FROM dbo.FactSales AS f
INNER JOIN dbo.DimCustomer AS c ON f.customer_id = c.customer_id
INNER JOIN dbo.DimRegion   AS r ON c.region_id   = r.region_id
GROUP BY r.region_name, r.country
ORDER BY total_revenue DESC;
GO

/* ------------------------------------------------------------
   2. Products with Revenue but Below-Average Margin
      (LEFT JOIN + GROUP BY + HAVING)
   ------------------------------------------------------------ */
SELECT
    p.product_id,
    p.product_name,
    p.category,
    SUM(f.net_revenue) AS total_revenue,
    SUM(f.profit)       AS total_profit,
    CAST(SUM(f.profit) * 100.0 / NULLIF(SUM(f.net_revenue), 0) AS DECIMAL(6,2)) AS margin_pct
FROM dbo.DimProduct AS p
LEFT JOIN dbo.FactSales AS f ON p.product_id = f.product_id
GROUP BY p.product_id, p.product_name, p.category
HAVING SUM(f.net_revenue) > 0
   AND SUM(f.profit) * 1.0 / NULLIF(SUM(f.net_revenue), 0) <
       (SELECT AVG(profit_margin_pct) FROM dbo.FactSales)
ORDER BY margin_pct ASC;
GO

/* ------------------------------------------------------------
   3. Monthly Revenue Trend with Running Total & MoM Growth
      (Window Functions: SUM OVER, LAG)
   ------------------------------------------------------------ */
WITH MonthlyRevenue AS (
    SELECT
        d.year,
        d.month,
        d.month_name,
        SUM(f.net_revenue) AS monthly_revenue,
        SUM(f.profit)       AS monthly_profit
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
    SUM(monthly_revenue) OVER (ORDER BY year, month
                                ROWS UNBOUNDED PRECEDING)                AS running_total_revenue,
    LAG(monthly_revenue) OVER (ORDER BY year, month)                    AS prev_month_revenue,
    CAST((monthly_revenue - LAG(monthly_revenue) OVER (ORDER BY year, month))
         * 100.0 / NULLIF(LAG(monthly_revenue) OVER (ORDER BY year, month), 0)
         AS DECIMAL(6,2))                                               AS mom_growth_pct
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
        SUM(f.net_revenue) AS total_revenue,
        RANK() OVER (PARTITION BY r.region_name ORDER BY SUM(f.net_revenue) DESC) AS revenue_rank
    FROM dbo.FactSales AS f
    INNER JOIN dbo.DimCustomer AS c ON f.customer_id = c.customer_id
    INNER JOIN dbo.DimRegion   AS r ON c.region_id   = r.region_id
    GROUP BY r.region_name, c.customer_id, c.customer_name
)
SELECT *
FROM CustomerRevenue
WHERE revenue_rank <= 5
ORDER BY region_name, revenue_rank;
GO

/* ------------------------------------------------------------
   5. Customer Growth by Signup Month (CTE)
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

/* ------------------------------------------------------------
   6. Inventory Turnover & Reorder Risk (LEFT JOIN + CASE)
   ------------------------------------------------------------ */
SELECT
    p.product_id,
    p.product_name,
    i.warehouse,
    i.stock_quantity,
    i.reorder_level,
    COALESCE(SUM(f.quantity), 0)                                        AS units_sold,
    CAST(COALESCE(SUM(f.quantity), 0) * 1.0 / NULLIF(i.stock_quantity, 0)
         AS DECIMAL(6,2))                                                AS turnover_ratio,
    CASE WHEN i.stock_quantity <= i.reorder_level THEN 'REORDER NOW' ELSE 'OK' END AS risk_flag
FROM dbo.DimInventory AS i
INNER JOIN dbo.DimProduct AS p ON i.product_id = p.product_id
LEFT JOIN dbo.FactSales AS f ON p.product_id = f.product_id
GROUP BY p.product_id, p.product_name, i.warehouse, i.stock_quantity, i.reorder_level
ORDER BY turnover_ratio DESC;
GO

/* ------------------------------------------------------------
   7. Average Order Value & Sales Growth by Quarter
   ------------------------------------------------------------ */
SELECT
    d.year,
    d.quarter,
    COUNT(DISTINCT f.order_id)                          AS total_orders,
    SUM(f.net_revenue)                                  AS total_revenue,
    CAST(SUM(f.net_revenue) * 1.0 / COUNT(DISTINCT f.order_id) AS DECIMAL(10,2)) AS avg_order_value
FROM dbo.FactSales AS f
INNER JOIN dbo.DimDate AS d ON f.date_id = d.date_id
GROUP BY d.year, d.quarter
ORDER BY d.year, d.quarter;
GO
