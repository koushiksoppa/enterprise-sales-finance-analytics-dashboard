"""
build_kpis.py
-------------
Reads the cleaned star-schema tables from data/processed/ and produces the
business KPI tables that back the reports/ folder, the executive insights
report, and the dashboard previews. They double as a sanity check against the
Power BI DAX measures: every table here has a documented DAX and T-SQL
equivalent in docs/KPI_DEFINITIONS.md.

Run:
    python build_kpis.py
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Customers whose source region_id failed referential integrity are parked in
# this bucket by clean_data.py. It is a data-quality artefact, not a market, so
# it is reported separately rather than ranked against real regions.
UNKNOWN_REGION_ID = "R00"
UNKNOWN_REGION_NAME = "Unknown / Unassigned"

# Months projected beyond the last actual month on the Forecast page.
FORECAST_HORIZON_MONTHS = 6
# ~95% band, derived from the residual spread of the in-sample fit.
FORECAST_Z = 1.96


def load_processed():
    fact_sales = pd.read_csv(PROCESSED_DIR / "FactSales.csv", parse_dates=["order_date"])
    dim_customer = pd.read_csv(PROCESSED_DIR / "DimCustomer.csv", parse_dates=["signup_date"])
    dim_product = pd.read_csv(PROCESSED_DIR / "DimProduct.csv")
    dim_region = pd.read_csv(PROCESSED_DIR / "DimRegion.csv")
    dim_inventory = pd.read_csv(PROCESSED_DIR / "DimInventory.csv")
    return fact_sales, dim_customer, dim_product, dim_region, dim_inventory


def build_sales_detail(
    fact_sales: pd.DataFrame,
    dim_customer: pd.DataFrame,
    dim_product: pd.DataFrame,
    dim_region: pd.DataFrame,
) -> pd.DataFrame:
    """One denormalized row per order line - the Python mirror of vw_SalesFlat."""
    logger.info("Denormalizing the fact table against the dimensions")
    detail = (
        fact_sales
        .merge(dim_customer[["customer_id", "customer_name", "segment", "region_id"]],
               on="customer_id", how="left")
        .merge(dim_region[["region_id", "region_name", "country"]], on="region_id", how="left")
        .merge(dim_product[["product_id", "product_name", "category", "unit_cost"]],
               on="product_id", how="left")
    )
    detail["region_id"] = detail["region_id"].fillna(UNKNOWN_REGION_ID)
    detail["region_name"] = detail["region_name"].fillna(UNKNOWN_REGION_NAME)
    detail["country"] = detail["country"].fillna("N/A")
    detail["month"] = detail["order_date"].dt.to_period("M")
    return detail


def _margin_pct(profit: pd.Series, revenue: pd.Series) -> pd.Series:
    """Revenue-weighted margin, in percent. Guards against divide-by-zero."""
    return (profit / revenue.replace(0, np.nan) * 100).round(2)


def monthly_sales_growth(detail: pd.DataFrame) -> pd.DataFrame:
    logger.info("Computing the monthly sales trend and growth rates")
    monthly = (
        detail.groupby("month")
        .agg(
            revenue=("net_revenue", "sum"),
            profit=("profit", "sum"),
            orders=("order_id", "nunique"),
            customers=("customer_id", "nunique"),
            units=("quantity", "sum"),
        )
        .reset_index()
        .sort_values("month")
    )
    monthly["avg_order_value"] = (monthly["revenue"] / monthly["orders"]).round(2)
    monthly["revenue_growth_pct"] = (monthly["revenue"].pct_change() * 100).round(2)
    # Same calendar month one year earlier: 12 rows back on a gap-free series.
    monthly["revenue_yoy_pct"] = (monthly["revenue"].pct_change(periods=12) * 100).round(2)
    monthly["profit_margin_pct"] = _margin_pct(monthly["profit"], monthly["revenue"])
    monthly["month"] = monthly["month"].astype(str)
    return monthly


def top_products(detail: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    logger.info("Ranking the top %s products by revenue", n)
    agg = (
        detail.groupby(["product_id", "product_name", "category"])
        .agg(total_revenue=("net_revenue", "sum"), total_profit=("profit", "sum"),
             units_sold=("quantity", "sum"), total_orders=("order_id", "nunique"))
        .reset_index()
    )
    agg["profit_margin_pct"] = _margin_pct(agg["total_profit"], agg["total_revenue"])
    return agg.sort_values("total_revenue", ascending=False).head(n).reset_index(drop=True)


def lowest_margin_products(detail: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    logger.info("Ranking the lowest-margin products")
    agg = (
        detail.groupby(["product_id", "product_name", "category"])
        .agg(total_revenue=("net_revenue", "sum"), total_profit=("profit", "sum"))
        .reset_index()
    )
    agg["margin_pct"] = _margin_pct(agg["total_profit"], agg["total_revenue"])
    return agg.sort_values("margin_pct", ascending=True).head(n).reset_index(drop=True)


def top_customers(detail: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    logger.info("Ranking the top %s customers by revenue", n)
    agg = (
        detail.groupby(["customer_id", "customer_name", "segment", "region_name"])
        .agg(total_revenue=("net_revenue", "sum"), total_profit=("profit", "sum"),
             total_orders=("order_id", "nunique"))
        .reset_index()
    )
    agg["avg_order_value"] = (agg["total_revenue"] / agg["total_orders"]).round(2)
    agg["profit_margin_pct"] = _margin_pct(agg["total_profit"], agg["total_revenue"])
    return agg.sort_values("total_revenue", ascending=False).head(n).reset_index(drop=True)


def regional_performance(detail: pd.DataFrame) -> pd.DataFrame:
    """Revenue and profit rolled up to the region grain.

    DimRegion carries one row per *country*, so region_name repeats across
    region_ids (three rows are "Asia Pacific"). Grouping on region_id here
    would split one region into several apparent regions, which is exactly
    what a region-level KPI must not do. The country grain is reported
    separately by country_performance().
    """
    logger.info("Computing regional performance")
    agg = (
        detail.groupby("region_name")
        .agg(total_revenue=("net_revenue", "sum"), total_profit=("profit", "sum"),
             total_orders=("order_id", "nunique"), total_customers=("customer_id", "nunique"),
             countries=("country", "nunique"))
        .reset_index()
    )
    agg["avg_order_value"] = (agg["total_revenue"] / agg["total_orders"]).round(2)
    agg["profit_margin_pct"] = _margin_pct(agg["total_profit"], agg["total_revenue"])
    agg["revenue_share_pct"] = (agg["total_revenue"] / agg["total_revenue"].sum() * 100).round(2)
    return agg.sort_values("total_revenue", ascending=False).reset_index(drop=True)


def country_performance(detail: pd.DataFrame) -> pd.DataFrame:
    """Country grain - the drill-down level beneath regional_performance()."""
    logger.info("Computing country performance")
    agg = (
        detail.groupby(["region_name", "country", "region_id"])
        .agg(total_revenue=("net_revenue", "sum"), total_profit=("profit", "sum"),
             total_orders=("order_id", "nunique"), total_customers=("customer_id", "nunique"))
        .reset_index()
    )
    agg["avg_order_value"] = (agg["total_revenue"] / agg["total_orders"]).round(2)
    agg["profit_margin_pct"] = _margin_pct(agg["total_profit"], agg["total_revenue"])
    return agg.sort_values("total_revenue", ascending=False).reset_index(drop=True)


def category_performance(detail: pd.DataFrame) -> pd.DataFrame:
    logger.info("Computing category performance")
    agg = (
        detail.groupby("category")
        .agg(total_revenue=("net_revenue", "sum"), total_profit=("profit", "sum"),
             total_orders=("order_id", "nunique"), units_sold=("quantity", "sum"),
             products=("product_id", "nunique"))
        .reset_index()
    )
    agg["avg_order_value"] = (agg["total_revenue"] / agg["total_orders"]).round(2)
    agg["profit_margin_pct"] = _margin_pct(agg["total_profit"], agg["total_revenue"])
    agg["revenue_share_pct"] = (agg["total_revenue"] / agg["total_revenue"].sum() * 100).round(2)
    return agg.sort_values("total_revenue", ascending=False).reset_index(drop=True)


def segment_performance(detail: pd.DataFrame) -> pd.DataFrame:
    """Customer-segment grain, including the repeat rate within each segment."""
    logger.info("Computing customer segment performance")
    agg = (
        detail.groupby("segment")
        .agg(total_revenue=("net_revenue", "sum"), total_profit=("profit", "sum"),
             total_orders=("order_id", "nunique"), total_customers=("customer_id", "nunique"))
        .reset_index()
    )
    orders_per_customer = detail.groupby(["segment", "customer_id"])["order_id"].nunique()
    repeat = (
        orders_per_customer.gt(1).groupby(level="segment").mean().mul(100).round(2)
        .rename("repeat_customer_rate_pct").reset_index()
    )
    agg = agg.merge(repeat, on="segment", how="left")
    agg["avg_order_value"] = (agg["total_revenue"] / agg["total_orders"]).round(2)
    agg["revenue_per_customer"] = (agg["total_revenue"] / agg["total_customers"]).round(2)
    agg["profit_margin_pct"] = _margin_pct(agg["total_profit"], agg["total_revenue"])
    agg["revenue_share_pct"] = (agg["total_revenue"] / agg["total_revenue"].sum() * 100).round(2)
    return agg.sort_values("total_revenue", ascending=False).reset_index(drop=True)


def customer_growth(dim_customer: pd.DataFrame, detail: pd.DataFrame) -> pd.DataFrame:
    """New signups per month, alongside how many customers actually transacted.

    The two series answer different questions and are deliberately kept apart:
    signups are an acquisition measure and start before the sales window,
    while active customers are a demand measure inside it.
    """
    logger.info("Computing the customer growth trend")
    growth = (
        dim_customer.assign(signup_month=dim_customer["signup_date"].dt.to_period("M"))
        .groupby("signup_month")
        .size()
        .reset_index(name="new_customers")
        .sort_values("signup_month")
    )
    growth["cumulative_customers"] = growth["new_customers"].cumsum()
    growth["customer_growth_pct"] = (growth["cumulative_customers"].pct_change() * 100).round(2)

    active = (
        detail.groupby("month")["customer_id"].nunique()
        .reset_index(name="active_customers").rename(columns={"month": "signup_month"})
    )
    growth = growth.merge(active, on="signup_month", how="left")
    growth["signup_month"] = growth["signup_month"].astype(str)
    return growth


def inventory_turnover(detail: pd.DataFrame, dim_inventory: pd.DataFrame,
                       dim_product: pd.DataFrame) -> pd.DataFrame:
    logger.info("Computing inventory turnover and reorder risk")
    units_sold = detail.groupby("product_id")["quantity"].sum().reset_index(name="units_sold")
    merged = (
        dim_inventory
        .merge(dim_product[["product_id", "product_name", "category", "unit_cost"]],
               on="product_id", how="left")
        .merge(units_sold, on="product_id", how="left")
    )
    merged["units_sold"] = merged["units_sold"].fillna(0)
    merged["turnover_ratio"] = np.where(
        merged["stock_quantity"] > 0, (merged["units_sold"] / merged["stock_quantity"]).round(2), 0
    )
    merged["stock_value"] = (merged["stock_quantity"] * merged["unit_cost"]).round(2)
    # Headroom above the reorder trigger; negative means the trigger is breached.
    merged["stock_vs_reorder"] = merged["stock_quantity"] - merged["reorder_level"]
    merged["risk_flag"] = np.select(
        [merged["stock_quantity"] <= merged["reorder_level"],
         merged["stock_quantity"] <= merged["reorder_level"] * 1.25],
        ["REORDER NOW", "AT RISK"],
        default="OK",
    )
    return merged.sort_values("turnover_ratio", ascending=False).reset_index(drop=True)


def revenue_forecast(monthly: pd.DataFrame) -> pd.DataFrame:
    """Project revenue forward with a seasonal linear-trend model.

    Method: ordinary least squares on the month index gives the underlying
    trend; that trend is multiplied by a month-of-year seasonal index (the
    mean ratio of actual to trend for that calendar month, normalized to
    average 1). The band is the fitted value +/- 1.96 residual standard
    deviations - an indication of historical dispersion, not a guarantee.
    """
    logger.info("Building the revenue forecast (seasonal linear trend, %s-month horizon)",
                FORECAST_HORIZON_MONTHS)
    hist = monthly[["month", "revenue"]].copy()
    hist["period"] = pd.PeriodIndex(hist["month"], freq="M")
    hist["month_index"] = np.arange(len(hist))

    slope, intercept = np.polyfit(hist["month_index"], hist["revenue"], 1)
    hist["linear_trend"] = intercept + slope * hist["month_index"]

    hist["calendar_month"] = hist["period"].map(lambda p: p.month)
    seasonal = (hist["revenue"] / hist["linear_trend"]).groupby(hist["calendar_month"]).mean()
    seasonal = seasonal / seasonal.mean()

    fitted = hist["linear_trend"] * hist["calendar_month"].map(seasonal)
    residual_std = float((hist["revenue"] - fitted).std(ddof=2))

    hist["moving_avg_3m"] = hist["revenue"].rolling(window=3, min_periods=1).mean().round(2)

    last_period = hist["period"].iloc[-1]
    future = pd.DataFrame({
        "period": [last_period + i for i in range(1, FORECAST_HORIZON_MONTHS + 1)],
        "month_index": np.arange(len(hist), len(hist) + FORECAST_HORIZON_MONTHS),
    })
    future["month"] = future["period"].astype(str)
    future["linear_trend"] = intercept + slope * future["month_index"]
    future["calendar_month"] = future["period"].map(lambda p: p.month)
    future["forecast_revenue"] = (future["linear_trend"]
                                  * future["calendar_month"].map(seasonal)).round(2)
    future["forecast_lower"] = (
        future["forecast_revenue"] - FORECAST_Z * residual_std).clip(lower=0).round(2)
    future["forecast_upper"] = (future["forecast_revenue"] + FORECAST_Z * residual_std).round(2)

    columns = ["month", "month_index", "is_forecast", "actual_revenue", "moving_avg_3m",
               "linear_trend", "forecast_revenue", "forecast_lower", "forecast_upper"]
    hist_out = hist.assign(is_forecast=0).rename(columns={"revenue": "actual_revenue"})
    future_out = future.assign(is_forecast=1, actual_revenue=np.nan, moving_avg_3m=np.nan)

    out = pd.concat([hist_out.reindex(columns=columns), future_out.reindex(columns=columns)],
                    ignore_index=True)
    out["linear_trend"] = out["linear_trend"].round(2)
    return out


def executive_summary(detail: pd.DataFrame, monthly: pd.DataFrame, dim_customer: pd.DataFrame,
                      inventory: pd.DataFrame) -> pd.DataFrame:
    """The headline KPI block.

    Single source for the insights report and the dashboard previews, so the
    numbers on the cover of the product cannot drift apart from the numbers in
    the detail tables.
    """
    logger.info("Building the executive summary KPI block")
    revenue = detail["net_revenue"].sum()
    profit = detail["profit"].sum()
    orders = detail["order_id"].nunique()
    customers = detail["customer_id"].nunique()

    orders_per_customer = detail.groupby("customer_id")["order_id"].nunique()
    repeat_rate = orders_per_customer.gt(1).mean() * 100

    latest = monthly.iloc[-1]
    prior = monthly.iloc[-2]
    by_year = monthly.assign(year=monthly["month"].str.slice(0, 4)).groupby("year")["revenue"].sum()
    yoy = (by_year.iloc[-1] / by_year.iloc[-2] - 1) * 100 if len(by_year) >= 2 else np.nan

    rows = [
        ("Total Revenue", revenue, "currency",
         "Sum of net revenue across all order lines"),
        ("Total Profit", profit, "currency",
         "Net revenue less total cost"),
        ("Profit Margin %", profit / revenue * 100, "percent",
         "Total profit / total revenue"),
        ("Total Orders", orders, "integer",
         "Distinct order identifiers"),
        ("Total Customers", customers, "integer",
         "Distinct customers with at least one order"),
        ("Average Order Value", revenue / orders, "currency",
         "Total revenue / total orders"),
        ("Revenue Growth MoM %", latest["revenue_growth_pct"], "percent",
         "Revenue change, " + str(prior["month"]) + " to " + str(latest["month"])),
        ("Revenue Growth YoY %", yoy, "percent",
         "Revenue change, " + str(by_year.index[-2]) + " to " + str(by_year.index[-1])),
        ("Repeat Customer Rate %", repeat_rate, "percent",
         "Customers with more than one order / all customers"),
        ("Units Sold", detail["quantity"].sum(), "integer",
         "Sum of order-line quantity"),
        ("Inventory Turnover Ratio",
         inventory["units_sold"].sum() / inventory["stock_quantity"].sum(), "ratio",
         "Units sold / units on hand"),
        ("Products At Reorder Level", int((inventory["risk_flag"] == "REORDER NOW").sum()),
         "integer", "Stock on hand at or below the reorder trigger"),
        ("Customers On File", len(dim_customer), "integer",
         "Rows in DimCustomer, including customers who have not yet ordered"),
    ]
    return pd.DataFrame(rows, columns=["metric", "value", "format", "definition"])


def main() -> None:
    fact_sales, dim_customer, dim_product, dim_region, dim_inventory = load_processed()
    detail = build_sales_detail(fact_sales, dim_customer, dim_product, dim_region)

    monthly = monthly_sales_growth(detail)
    inventory = inventory_turnover(detail, dim_inventory, dim_product)

    outputs = {
        "kpi_executive_summary.csv": executive_summary(detail, monthly, dim_customer, inventory),
        "kpi_monthly_sales_growth.csv": monthly,
        "kpi_top_10_products.csv": top_products(detail),
        "kpi_lowest_margin_products.csv": lowest_margin_products(detail),
        "kpi_top_10_customers.csv": top_customers(detail),
        "kpi_regional_performance.csv": regional_performance(detail),
        "kpi_country_performance.csv": country_performance(detail),
        "kpi_category_performance.csv": category_performance(detail),
        "kpi_segment_performance.csv": segment_performance(detail),
        "kpi_customer_growth.csv": customer_growth(dim_customer, detail),
        "kpi_inventory_turnover.csv": inventory,
        "kpi_revenue_forecast.csv": revenue_forecast(monthly),
    }

    for filename, df in outputs.items():
        path = REPORTS_DIR / filename
        df.to_csv(path, index=False)
        logger.info("Wrote %s (%s rows)", path.name, len(df))

    logger.info("All KPI tables written to %s", REPORTS_DIR)


if __name__ == "__main__":
    main()
