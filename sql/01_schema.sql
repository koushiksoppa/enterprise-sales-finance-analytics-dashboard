/* ============================================================
   01_schema.sql
   Star Schema DDL for Enterprise Sales & Finance Analytics
   Target: Microsoft SQL Server 2019+ / Azure SQL
   ============================================================ */

IF DB_ID('SalesAnalyticsDW') IS NULL
BEGIN
    CREATE DATABASE SalesAnalyticsDW;
END
GO

USE SalesAnalyticsDW;
GO

/* ---------- DIMENSION: DimRegion ---------- */
IF OBJECT_ID('dbo.DimRegion', 'U') IS NOT NULL DROP TABLE dbo.DimRegion;
GO
CREATE TABLE dbo.DimRegion (
    region_id      VARCHAR(10)   NOT NULL PRIMARY KEY,
    region_name    VARCHAR(50)   NOT NULL,
    country        VARCHAR(50)   NOT NULL
);
GO

/* ---------- DIMENSION: DimCustomer ---------- */
IF OBJECT_ID('dbo.DimCustomer', 'U') IS NOT NULL DROP TABLE dbo.DimCustomer;
GO
CREATE TABLE dbo.DimCustomer (
    customer_id    VARCHAR(10)   NOT NULL PRIMARY KEY,
    customer_name  VARCHAR(150)  NOT NULL,
    email          VARCHAR(150)  NULL,
    segment        VARCHAR(30)   NOT NULL,
    region_id      VARCHAR(10)   NOT NULL,
    signup_date    DATE          NOT NULL,
    CONSTRAINT FK_DimCustomer_Region FOREIGN KEY (region_id)
        REFERENCES dbo.DimRegion (region_id)
);
GO

/* ---------- DIMENSION: DimProduct ---------- */
IF OBJECT_ID('dbo.DimProduct', 'U') IS NOT NULL DROP TABLE dbo.DimProduct;
GO
CREATE TABLE dbo.DimProduct (
    product_id     VARCHAR(10)    NOT NULL PRIMARY KEY,
    product_name   VARCHAR(150)   NOT NULL,
    category       VARCHAR(50)    NOT NULL,
    unit_cost      DECIMAL(10,2)  NOT NULL,
    unit_price     DECIMAL(10,2)  NOT NULL,
    margin_pct     DECIMAL(6,4)   NOT NULL
);
GO

/* ---------- DIMENSION: DimInventory ---------- */
IF OBJECT_ID('dbo.DimInventory', 'U') IS NOT NULL DROP TABLE dbo.DimInventory;
GO
CREATE TABLE dbo.DimInventory (
    inventory_id       INT IDENTITY(1,1) PRIMARY KEY,
    product_id         VARCHAR(10)    NOT NULL,
    warehouse          VARCHAR(20)    NOT NULL,
    stock_quantity     INT            NOT NULL,
    reorder_level      INT            NOT NULL,
    last_restock_date  DATE           NULL,
    needs_reorder      BIT            NOT NULL DEFAULT 0,
    CONSTRAINT FK_DimInventory_Product FOREIGN KEY (product_id)
        REFERENCES dbo.DimProduct (product_id)
);
GO

/* ---------- DIMENSION: DimDate ---------- */
IF OBJECT_ID('dbo.DimDate', 'U') IS NOT NULL DROP TABLE dbo.DimDate;
GO
CREATE TABLE dbo.DimDate (
    date_id        INT           NOT NULL PRIMARY KEY,   -- YYYYMMDD
    full_date      DATE          NOT NULL,
    year           INT           NOT NULL,
    quarter        INT           NOT NULL,
    month          INT           NOT NULL,
    month_name     VARCHAR(15)   NOT NULL,
    day            INT           NOT NULL,
    day_name       VARCHAR(15)   NOT NULL,
    week_of_year   INT           NOT NULL,
    is_weekend     BIT           NOT NULL,
    fiscal_year    INT           NOT NULL
);
GO

/* ---------- FACT: FactSales ---------- */
IF OBJECT_ID('dbo.FactSales', 'U') IS NOT NULL DROP TABLE dbo.FactSales;
GO
CREATE TABLE dbo.FactSales (
    order_id           VARCHAR(15)    NOT NULL PRIMARY KEY,
    date_id            INT            NOT NULL,
    customer_id        VARCHAR(10)    NOT NULL,
    product_id         VARCHAR(10)    NOT NULL,
    quantity           INT            NOT NULL,
    unit_price         DECIMAL(10,2)  NOT NULL,
    discount_pct       DECIMAL(5,4)   NOT NULL DEFAULT 0,
    gross_amount       DECIMAL(12,2)  NOT NULL,
    discount_amount    DECIMAL(12,2)  NOT NULL DEFAULT 0,
    net_revenue        DECIMAL(12,2)  NOT NULL,
    total_cost         DECIMAL(12,2)  NOT NULL,
    profit             DECIMAL(12,2)  NOT NULL,
    profit_margin_pct  DECIMAL(6,4)   NOT NULL,
    CONSTRAINT FK_FactSales_Date     FOREIGN KEY (date_id)     REFERENCES dbo.DimDate (date_id),
    CONSTRAINT FK_FactSales_Customer FOREIGN KEY (customer_id) REFERENCES dbo.DimCustomer (customer_id),
    CONSTRAINT FK_FactSales_Product  FOREIGN KEY (product_id)  REFERENCES dbo.DimProduct (product_id)
);
GO

/* ============================================================
   INDEXES  (query performance on the fact table)
   ============================================================ */
CREATE NONCLUSTERED INDEX IX_FactSales_DateId       ON dbo.FactSales (date_id);
CREATE NONCLUSTERED INDEX IX_FactSales_CustomerId    ON dbo.FactSales (customer_id);
CREATE NONCLUSTERED INDEX IX_FactSales_ProductId     ON dbo.FactSales (product_id);
CREATE NONCLUSTERED INDEX IX_FactSales_Date_Customer ON dbo.FactSales (date_id, customer_id) INCLUDE (net_revenue, profit);
CREATE NONCLUSTERED INDEX IX_DimCustomer_Region      ON dbo.DimCustomer (region_id);
CREATE NONCLUSTERED INDEX IX_DimInventory_Product    ON dbo.DimInventory (product_id);
GO
