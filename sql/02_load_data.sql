/* ============================================================
   02_load_data.sql
   Bulk-loads the cleaned star-schema CSVs (produced by
   python/clean_data.py) into SQL Server using BULK INSERT.

   IMPORTANT (Windows):
   Update the file paths below to the absolute Windows path of your
   cloned repo, e.g.:
       D:\Projects\enterprise-sales-finance-analytics-dashboard\data\processed\
   Run 01_schema.sql first, and python/prepare_sql_csv.py before that so the
   *_ForSql.csv files exist with the column order the DDL expects.

   ROWTERMINATOR is 0x0d0a, not '\n'. pandas writes CRLF line endings on
   Windows; with '\n' the carriage return is carried into the last column of
   every row, which either silently appends \r to a trailing text column or
   fails type conversion on a trailing numeric one.
   ============================================================ */

USE SalesAnalyticsDW;
GO

DECLARE @DataPath NVARCHAR(500) =
    N'D:\Projects\enterprise-sales-finance-analytics-dashboard\data\processed\';

-- ---------- DimRegion ----------
TRUNCATE TABLE dbo.DimRegion;
DECLARE @sql NVARCHAR(MAX);
SET @sql = N'
BULK INSERT dbo.DimRegion
FROM ''' + @DataPath + N'DimRegion.csv''
WITH (FORMAT = ''CSV'', FIRSTROW = 2, FIELDTERMINATOR = '','', ROWTERMINATOR = ''0x0d0a'', TABLOCK);';
EXEC sp_executesql @sql;

-- ---------- DimCustomer ----------
-- Note: source CSV column order = customer_id, customer_name, email, segment, region_id, signup_date
DELETE FROM dbo.DimCustomer;
SET @sql = N'
BULK INSERT dbo.DimCustomer
FROM ''' + @DataPath + N'DimCustomer.csv''
WITH (FORMAT = ''CSV'', FIRSTROW = 2, FIELDTERMINATOR = '','', ROWTERMINATOR = ''0x0d0a'', TABLOCK);';
EXEC sp_executesql @sql;

-- ---------- DimProduct ----------
DELETE FROM dbo.DimProduct;
SET @sql = N'
BULK INSERT dbo.DimProduct
FROM ''' + @DataPath + N'DimProduct.csv''
WITH (FORMAT = ''CSV'', FIRSTROW = 2, FIELDTERMINATOR = '','', ROWTERMINATOR = ''0x0d0a'', TABLOCK);';
EXEC sp_executesql @sql;

-- ---------- DimInventory ----------
-- source columns: product_id, warehouse, stock_quantity, reorder_level, last_restock_date, needs_reorder
DELETE FROM dbo.DimInventory;
SET @sql = N'
BULK INSERT dbo.DimInventory
FROM ''' + @DataPath + N'DimInventory_ForSql.csv''
WITH (FORMAT = ''CSV'', FIRSTROW = 2, FIELDTERMINATOR = '','', ROWTERMINATOR = ''0x0d0a'', TABLOCK);';
EXEC sp_executesql @sql;

-- ---------- DimDate ----------
DELETE FROM dbo.DimDate;
SET @sql = N'
BULK INSERT dbo.DimDate
FROM ''' + @DataPath + N'DimDate.csv''
WITH (FORMAT = ''CSV'', FIRSTROW = 2, FIELDTERMINATOR = '','', ROWTERMINATOR = ''0x0d0a'', TABLOCK);';
EXEC sp_executesql @sql;

-- ---------- FactSales ----------
DELETE FROM dbo.FactSales;
SET @sql = N'
BULK INSERT dbo.FactSales
FROM ''' + @DataPath + N'FactSales_ForSql.csv''
WITH (FORMAT = ''CSV'', FIRSTROW = 2, FIELDTERMINATOR = '','', ROWTERMINATOR = ''0x0d0a'', TABLOCK);';
EXEC sp_executesql @sql;

PRINT 'Data load complete.';
GO

/* ------------------------------------------------------------
   NOTE: FactSales.csv / DimInventory.csv as produced by
   clean_data.py include extra pandas-derived columns in a
   different order than the SQL DDL. Run:
       python python/prepare_sql_csv.py
   (see python/ folder) to emit DimInventory_ForSql.csv and
   FactSales_ForSql.csv with exact column order matching the
   DDL above before running this script.
   ------------------------------------------------------------ */
