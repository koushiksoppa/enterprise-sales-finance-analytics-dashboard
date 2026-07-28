/* ============================================================
   02_load_data.sql
   Bulk-loads the cleaned star-schema CSVs (produced by
   python/clean_data.py) into SQL Server using BULK INSERT.

   IMPORTANT (Windows):
   Update the file paths below to the absolute Windows path of your
   cloned repo, e.g.:
       C:\Projects\Enterprise-Sales-Finance-Analytics-Dashboard\data\processed\
   Run 01_schema.sql first.
   ============================================================ */

USE SalesAnalyticsDW;
GO

DECLARE @DataPath NVARCHAR(500) =
    N'C:\Projects\Enterprise-Sales-Finance-Analytics-Dashboard\data\processed\';

-- ---------- DimRegion ----------
TRUNCATE TABLE dbo.DimRegion;
DECLARE @sql NVARCHAR(MAX);
SET @sql = N'
BULK INSERT dbo.DimRegion
FROM ''' + @DataPath + N'DimRegion.csv''
WITH (FORMAT = ''CSV'', FIRSTROW = 2, FIELDTERMINATOR = '','', ROWTERMINATOR = ''\n'', TABLOCK);';
EXEC sp_executesql @sql;

-- ---------- DimCustomer ----------
-- Note: source CSV column order = customer_id, customer_name, email, segment, region_id, signup_date
DELETE FROM dbo.DimCustomer;
SET @sql = N'
BULK INSERT dbo.DimCustomer
FROM ''' + @DataPath + N'DimCustomer.csv''
WITH (FORMAT = ''CSV'', FIRSTROW = 2, FIELDTERMINATOR = '','', ROWTERMINATOR = ''\n'', TABLOCK);';
EXEC sp_executesql @sql;

-- ---------- DimProduct ----------
DELETE FROM dbo.DimProduct;
SET @sql = N'
BULK INSERT dbo.DimProduct
FROM ''' + @DataPath + N'DimProduct.csv''
WITH (FORMAT = ''CSV'', FIRSTROW = 2, FIELDTERMINATOR = '','', ROWTERMINATOR = ''\n'', TABLOCK);';
EXEC sp_executesql @sql;

-- ---------- DimInventory ----------
-- source columns: product_id, warehouse, stock_quantity, reorder_level, last_restock_date, needs_reorder
SET IDENTITY_INSERT dbo.DimInventory OFF;
DELETE FROM dbo.DimInventory;
SET @sql = N'
BULK INSERT dbo.DimInventory
FROM ''' + @DataPath + N'DimInventory_ForSql.csv''
WITH (FORMAT = ''CSV'', FIRSTROW = 2, FIELDTERMINATOR = '','', ROWTERMINATOR = ''\n'', TABLOCK);';
EXEC sp_executesql @sql;

-- ---------- DimDate ----------
DELETE FROM dbo.DimDate;
SET @sql = N'
BULK INSERT dbo.DimDate
FROM ''' + @DataPath + N'DimDate.csv''
WITH (FORMAT = ''CSV'', FIRSTROW = 2, FIELDTERMINATOR = '','', ROWTERMINATOR = ''\n'', TABLOCK);';
EXEC sp_executesql @sql;

-- ---------- FactSales ----------
DELETE FROM dbo.FactSales;
SET @sql = N'
BULK INSERT dbo.FactSales
FROM ''' + @DataPath + N'FactSales_ForSql.csv''
WITH (FORMAT = ''CSV'', FIRSTROW = 2, FIELDTERMINATOR = '','', ROWTERMINATOR = ''\n'', TABLOCK);';
EXEC sp_executesql @sql;

PRINT 'Data load complete.';
GO

/* ------------------------------------------------------------
   NOTE: FactSales.csv / DimInventory.csv as produced by
   clean_data.py include extra pandas-derived columns in a
   different order than the SQL DDL. Run:
       python sql/prepare_sql_csv.py
   (see python/ folder) to emit DimInventory_ForSql.csv and
   FactSales_ForSql.csv with exact column order matching the
   DDL above before running this script.
   ------------------------------------------------------------ */
