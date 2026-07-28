// ============================================================
// power_query_m.pq
// Power Query M code for each table. In Power BI Desktop:
//   Home > Transform Data > Home > Advanced Editor
// Create a Blank Query per table below, paste the corresponding
// M code, and rename the query to match the table name (e.g. FactSales).
//
// Update FolderPath to your local cloned repo path, e.g.:
//   "C:\Projects\Enterprise-Sales-Finance-Analytics-Dashboard\data\processed\"
// ============================================================

// ---------- Shared parameter (create as a Power Query Parameter named FolderPath) ----------
// FolderPath = "C:\Projects\Enterprise-Sales-Finance-Analytics-Dashboard\data\processed\"

// ---------- DimDate ----------
let
    Source = Csv.Document(File.Contents(FolderPath & "DimDate.csv"), [Delimiter=",", Columns=11, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    ChangedType = Table.TransformColumnTypes(PromotedHeaders, {
        {"date_id", Int64.Type}, {"full_date", type date}, {"year", Int64.Type},
        {"quarter", Int64.Type}, {"month", Int64.Type}, {"month_name", type text},
        {"day", Int64.Type}, {"day_name", type text}, {"week_of_year", Int64.Type},
        {"is_weekend", type logical}, {"fiscal_year", Int64.Type}
    })
in
    ChangedType

// ---------- DimCustomer ----------
let
    Source = Csv.Document(File.Contents(FolderPath & "DimCustomer.csv"), [Delimiter=",", Columns=6, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    ChangedType = Table.TransformColumnTypes(PromotedHeaders, {
        {"customer_id", type text}, {"customer_name", type text}, {"email", type text},
        {"segment", type text}, {"region_id", type text}, {"signup_date", type date}
    }),
    TrimmedNames = Table.TransformColumns(ChangedType, {{"customer_name", Text.Trim}})
in
    TrimmedNames

// ---------- DimProduct ----------
let
    Source = Csv.Document(File.Contents(FolderPath & "DimProduct.csv"), [Delimiter=",", Columns=5, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    ChangedType = Table.TransformColumnTypes(PromotedHeaders, {
        {"product_id", type text}, {"product_name", type text}, {"category", type text},
        {"unit_cost", type number}, {"unit_price", type number}, {"margin_pct", type number}
    })
in
    ChangedType

// ---------- DimRegion ----------
let
    Source = Csv.Document(File.Contents(FolderPath & "DimRegion.csv"), [Delimiter=",", Columns=3, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    ChangedType = Table.TransformColumnTypes(PromotedHeaders, {
        {"region_id", type text}, {"region_name", type text}, {"country", type text}
    })
in
    ChangedType

// ---------- DimInventory ----------
let
    Source = Csv.Document(File.Contents(FolderPath & "DimInventory.csv"), [Delimiter=",", Columns=6, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    ChangedType = Table.TransformColumnTypes(PromotedHeaders, {
        {"product_id", type text}, {"warehouse", type text}, {"stock_quantity", Int64.Type},
        {"reorder_level", Int64.Type}, {"last_restock_date", type date}, {"needs_reorder", type logical}
    })
in
    ChangedType

// ---------- FactSales ----------
let
    Source = Csv.Document(File.Contents(FolderPath & "FactSales.csv"), [Delimiter=",", Columns=14, Encoding=65001, QuoteStyle=QuoteStyle.None]),
    PromotedHeaders = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    ChangedType = Table.TransformColumnTypes(PromotedHeaders, {
        {"order_id", type text}, {"order_date", type date}, {"customer_id", type text},
        {"product_id", type text}, {"quantity", Int64.Type}, {"unit_price", type number},
        {"discount_pct", type number}, {"gross_amount", type number}, {"discount_amount", type number},
        {"net_revenue", type number}, {"total_cost", type number}, {"date_id", Int64.Type},
        {"profit", type number}, {"profit_margin_pct", type number}
    }),
    // Defensive filter: guarantee no negative/zero quantities reach the model
    FilteredRows = Table.SelectRows(ChangedType, each [quantity] > 0)
in
    FilteredRows
