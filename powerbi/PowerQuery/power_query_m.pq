// ============================================================
// power_query_m.pq
// Power Query M code for each table. In Power BI Desktop:
//   Home > Transform Data > Home > Advanced Editor
// Create a Blank Query per table below, paste the corresponding
// M code, and rename the query to match the table name (e.g. FactSales).
//
// Update FolderPath to your local cloned repo path, e.g.:
//   "D:\Projects\enterprise-sales-finance-analytics-dashboard\data\processed\"
// The trailing backslash is required.
//
// NOTES ON THE SOURCE FILES
// - Run the Python pipeline first; these queries read data/processed/.
// - Run prepare_sql_csv.py before loading. It normalises DimDate.csv column
//   order and writes is_weekend as 1/0, which is what the DimDate query below
//   expects. Loading a DimDate.csv that has not been through that step will
//   fail on the is_weekend conversion.
// - QuoteStyle.Csv (not QuoteStyle.None) so a quoted field containing a comma
//   is parsed as one value rather than splitting the row.
// ============================================================

// ---------- Shared parameter (create as a Power Query Parameter named FolderPath) ----------
// FolderPath = "D:\Projects\enterprise-sales-finance-analytics-dashboard\data\processed\"

// ---------- DimDate ----------
let
    Source = Csv.Document(File.Contents(FolderPath & "DimDate.csv"), [Delimiter=",", Columns=11, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    ChangedType = Table.TransformColumnTypes(PromotedHeaders, {
        {"date_id", Int64.Type}, {"full_date", type date}, {"year", Int64.Type},
        {"quarter", Int64.Type}, {"month", Int64.Type}, {"month_name", type text},
        {"day", Int64.Type}, {"day_name", type text}, {"week_of_year", Int64.Type},
        {"is_weekend", Int64.Type}, {"fiscal_year", Int64.Type}
    }),
    // prepare_sql_csv.py writes is_weekend as 1/0 for the SQL BIT column.
    // Text-to-logical coercion does not handle "1"/"0", so convert explicitly.
    WeekendFlag = Table.TransformColumns(ChangedType, {{"is_weekend", each _ = 1, type logical}}),
    // Month-name sort order for the report; without this, charts sort April first.
    MonthSort = Table.AddColumn(WeekendFlag, "month_sort", each [month], Int64.Type)
in
    MonthSort

// ---------- DimCustomer ----------
let
    Source = Csv.Document(File.Contents(FolderPath & "DimCustomer.csv"), [Delimiter=",", Columns=6, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    ChangedType = Table.TransformColumnTypes(PromotedHeaders, {
        {"customer_id", type text}, {"customer_name", type text}, {"email", type text},
        {"segment", type text}, {"region_id", type text}, {"signup_date", type date}
    }),
    TrimmedNames = Table.TransformColumns(ChangedType, {{"customer_name", Text.Trim}})
in
    TrimmedNames

// ---------- DimProduct ----------
// Six columns: product_id, product_name, category, unit_cost, unit_price, margin_pct.
let
    Source = Csv.Document(File.Contents(FolderPath & "DimProduct.csv"), [Delimiter=",", Columns=6, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    ChangedType = Table.TransformColumnTypes(PromotedHeaders, {
        {"product_id", type text}, {"product_name", type text}, {"category", type text},
        {"unit_cost", type number}, {"unit_price", type number}, {"margin_pct", type number}
    })
in
    ChangedType

// ---------- DimRegion ----------
// Grain is one row per COUNTRY, so region_name repeats (three rows are
// "Asia Pacific"). Group by region_name for region-level visuals and use
// country as the drill-down level beneath it. R00 "Unknown / Unassigned" is
// the bucket for customers whose source region failed referential integrity.
let
    Source = Csv.Document(File.Contents(FolderPath & "DimRegion.csv"), [Delimiter=",", Columns=3, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    ChangedType = Table.TransformColumnTypes(PromotedHeaders, {
        {"region_id", type text}, {"region_name", type text}, {"country", type text}
    })
in
    ChangedType

// ---------- DimInventory ----------
let
    Source = Csv.Document(File.Contents(FolderPath & "DimInventory.csv"), [Delimiter=",", Columns=6, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    ChangedType = Table.TransformColumnTypes(PromotedHeaders, {
        {"product_id", type text}, {"warehouse", type text}, {"stock_quantity", Int64.Type},
        {"reorder_level", Int64.Type}, {"last_restock_date", type date}, {"needs_reorder", type logical}
    }),
    // Headroom above the reorder trigger, used by the Inventory Analytics page
    // to sort the replenishment watchlist.
    Headroom = Table.AddColumn(ChangedType, "stock_vs_reorder",
        each [stock_quantity] - [reorder_level], Int64.Type)
in
    Headroom

// ---------- FactSales ----------
let
    Source = Csv.Document(File.Contents(FolderPath & "FactSales.csv"), [Delimiter=",", Columns=14, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    ChangedType = Table.TransformColumnTypes(PromotedHeaders, {
        {"order_id", type text}, {"order_date", type date}, {"customer_id", type text},
        {"product_id", type text}, {"quantity", Int64.Type}, {"unit_price", type number},
        {"discount_pct", type number}, {"gross_amount", type number}, {"discount_amount", type number},
        {"net_revenue", type number}, {"total_cost", type number}, {"date_id", Int64.Type},
        {"profit", type number}, {"profit_margin_pct", type number}
    }),
    // Defensive filter: guarantee no negative/zero quantities reach the model
    // even if the file was produced by an older run of the ETL.
    FilteredRows = Table.SelectRows(ChangedType, each [quantity] > 0)
in
    FilteredRows
