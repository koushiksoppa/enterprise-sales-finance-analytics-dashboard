/* ============================================================
   05_auto_retail_market.sql
   Auto-retail market layer: REAL FADA OEM-wise retail data
   (Feb-Sep 2026 vs the same months of 2025), all-India.
   Target: Microsoft SQL Server 2019+ / Azure SQL

   Answers, for a dealer group holding Toyota, Honda Cars, JSW MG Motor,
   Mercedes-Benz and Ather franchises:
     - Which brands gained or lost market share?
     - Did each portfolio brand grow faster or slower than its segment?
     - How did share move month by month?

   Load order: run 01_schema.sql first (creates SalesAnalyticsDW), then
   this file. Update @DataPath to your clone's data\external\ folder.
   The same figures are produced in Python by python/auto_retail_analysis.py.
   ============================================================ */

USE SalesAnalyticsDW;
GO

/* ---------- Tables ---------- */
IF OBJECT_ID('dbo.FactOemRetail', 'U') IS NOT NULL DROP TABLE dbo.FactOemRetail;
GO
CREATE TABLE dbo.FactOemRetail (
    month_key    CHAR(7)       NOT NULL,   -- 'YYYY-MM' of the 2026 month
    segment      VARCHAR(4)    NOT NULL,   -- 'PV' passenger vehicles, '2W' two-wheelers
    oem          VARCHAR(80)   NOT NULL,   -- FADA legal-entity name
    units_2026   INT           NOT NULL,
    units_2025   INT           NOT NULL,   -- same month, previous year
    CONSTRAINT PK_FactOemRetail PRIMARY KEY (month_key, segment, oem)
);
GO

IF OBJECT_ID('dbo.DimPortfolioBrand', 'U') IS NOT NULL DROP TABLE dbo.DimPortfolioBrand;
GO
CREATE TABLE dbo.DimPortfolioBrand (
    oem          VARCHAR(80)   NOT NULL PRIMARY KEY,
    brand        VARCHAR(40)   NOT NULL
);
INSERT INTO dbo.DimPortfolioBrand (oem, brand) VALUES
    ('TOYOTA KIRLOSKAR MOTOR PVT LTD', 'Toyota'),
    ('HONDA CARS INDIA LTD',           'Honda Cars'),
    ('JSW MG MOTOR INDIA PVT LTD',     'MG Motor'),
    ('MERCEDES-BENZ GROUP',            'Mercedes-Benz'),
    ('ATHER ENERGY LTD',               'Ather');
GO

/* ---------- Load ---------- */
DECLARE @DataPath NVARCHAR(500) =
    N'D:\Projects\enterprise-sales-finance-analytics-dashboard\data\external\';
DECLARE @sql NVARCHAR(MAX) = N'
BULK INSERT dbo.FactOemRetail
FROM ''' + @DataPath + N'fada_oem_retail_2026.csv''
WITH (FORMAT = ''CSV'', FIRSTROW = 2, FIELDQUOTE = ''"'', ROWTERMINATOR = ''0x0a'', TABLOCK);';
EXEC sp_executesql @sql;
GO

/* Bajaj and Greaves are reported under two names across months; unify them
   so each company is one entity (mirrors the Python load step). */
UPDATE dbo.FactOemRetail SET oem = 'BAJAJ AUTO LTD' WHERE oem = 'BAJAJ AUTO GROUP';
UPDATE dbo.FactOemRetail SET oem = 'GREAVES ELECTRIC MOBILITY LTD'
WHERE oem = 'GREAVES ELECTRIC MOBILITY PVT LTD';
GO

/* ---------- View: period market share and growth per OEM ---------- */
CREATE OR ALTER VIEW dbo.vw_OemPeriodPerformance AS
WITH oem_period AS (
    SELECT segment, oem,
           SUM(CAST(units_2026 AS BIGINT)) AS units_2026,
           SUM(CAST(units_2025 AS BIGINT)) AS units_2025
    FROM dbo.FactOemRetail
    GROUP BY segment, oem
),
segment_period AS (
    SELECT segment,
           SUM(units_2026) AS seg_2026,
           SUM(units_2025) AS seg_2025
    FROM oem_period
    GROUP BY segment
)
SELECT
    o.segment,
    o.oem,
    COALESCE(b.brand, o.oem)                                        AS brand,
    CASE WHEN b.oem IS NULL THEN 0 ELSE 1 END                       AS is_portfolio_brand,
    o.units_2026,
    o.units_2025,
    100.0 * (o.units_2026 - o.units_2025) / NULLIF(o.units_2025, 0) AS yoy_growth_pct,
    100.0 * (s.seg_2026 - s.seg_2025) / s.seg_2025                  AS segment_growth_pct,
    100.0 * o.units_2026 / s.seg_2026                               AS share_2026_pct,
    100.0 * o.units_2025 / s.seg_2025                               AS share_2025_pct,
    10000.0 * (1.0 * o.units_2026 / s.seg_2026
             - 1.0 * o.units_2025 / s.seg_2025)                     AS share_change_bps
FROM oem_period o
JOIN segment_period s ON s.segment = o.segment
LEFT JOIN dbo.DimPortfolioBrand b ON b.oem = o.oem;
GO

/* ---------- Q1. Who gained and lost passenger-vehicle share? ---------- */
SELECT brand, units_2026, CAST(share_2026_pct AS DECIMAL(6,2)) AS share_pct,
       CAST(share_change_bps AS DECIMAL(8,1)) AS share_change_bps,
       RANK() OVER (ORDER BY share_change_bps DESC) AS gain_rank
FROM dbo.vw_OemPeriodPerformance
WHERE segment = 'PV' AND oem <> 'Others'
ORDER BY share_change_bps DESC;

/* ---------- Q2. Portfolio brands: growth versus their own segment ---------- */
SELECT brand, segment,
       CAST(yoy_growth_pct AS DECIMAL(6,2))                       AS brand_growth_pct,
       CAST(segment_growth_pct AS DECIMAL(6,2))                   AS segment_growth_pct,
       CAST(yoy_growth_pct - segment_growth_pct AS DECIMAL(6,2))  AS growth_vs_market_pts,
       CASE WHEN yoy_growth_pct >= segment_growth_pct
            THEN 'Outgrowing market' ELSE 'Losing share' END      AS verdict
FROM dbo.vw_OemPeriodPerformance
WHERE is_portfolio_brand = 1
ORDER BY growth_vs_market_pts DESC;

/* ---------- Q3. Portfolio car brands combined: share lost, in units ---------- */
WITH pv AS (
    SELECT SUM(units_2026) AS u26, SUM(units_2025) AS u25 FROM dbo.vw_OemPeriodPerformance
    WHERE segment = 'PV' AND is_portfolio_brand = 1
), seg AS (
    SELECT SUM(units_2026) AS t26, SUM(units_2025) AS t25 FROM dbo.vw_OemPeriodPerformance
    WHERE segment = 'PV'
)
SELECT u26 AS portfolio_units_2026,
       CAST(100.0 * u26 / t26 AS DECIMAL(6,2))                     AS share_2026_pct,
       CAST(100.0 * u25 / t25 AS DECIMAL(6,2))                     AS share_2025_pct,
       CAST(ROUND(1.0 * u25 / t25 * t26, 0) AS INT) - u26          AS units_short_of_held_share
FROM pv CROSS JOIN seg;

/* ---------- Q4. Monthly share trend and month-on-month change (window functions) ---------- */
WITH monthly AS (
    SELECT f.month_key, f.segment, b.brand, f.units_2026,
           100.0 * f.units_2026 / SUM(f.units_2026) OVER (PARTITION BY f.month_key, f.segment) AS share_pct,
           100.0 * f.units_2025 / SUM(f.units_2025) OVER (PARTITION BY f.month_key, f.segment) AS share_ly_pct
    FROM dbo.FactOemRetail f
    LEFT JOIN dbo.DimPortfolioBrand b ON b.oem = f.oem
)
SELECT month_key, brand,
       CAST(share_pct AS DECIMAL(6,2))                                          AS share_pct,
       CAST(share_pct - share_ly_pct AS DECIMAL(6,2))                           AS share_change_vs_ly_pts,
       CAST(share_pct - LAG(share_pct) OVER (PARTITION BY brand ORDER BY month_key)
            AS DECIMAL(6,2))                                                    AS share_change_mom_pts
FROM monthly
WHERE brand IS NOT NULL
ORDER BY brand, month_key;
