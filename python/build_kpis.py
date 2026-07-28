"""
build_kpis.py
-------------
Reads the cleaned star-schema tables from data/processed/ and produces
business KPI tables used by the reports/ folder and as a sanity check
against the Power BI DAX measures.

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


def load_processed():
    fact_sales = pd.read_csv(PROCESSED_DIR / "FactSales.csv", parse_dates=["order_date"])
    dim_customer = pd.read_csv(PROCESSED_DIR / "DimCustomer.csv", parse_dates=["signup_date"])
    dim_product = pd.read_csv(PROCESSED_DIR / "DimProduct.csv")
    dim_region = pd.read_csv(PROCESSED_DIR / "DimRegion.csv")
    dim_inventory = pd.read_csv(PROCESSED_DIR / "DimInventory.csv")
    return fact_sales, dim_customer, dim_product, dim_region, dim_inventory


def monthly_sales_growth(fact_sales: pd.DataFrame) -> pd.DataFrame:
    logger.info("Computing monthly sales growth")
    monthly = (
        fact_sales.assign(month=fact_sales["order_date"].dt.to_period("M"))
        .groupby("month")
        .agg(revenue=("net_revenue", "sum"), profit=("profit", "sum"), orders=("order_id", "nunique"))
        .reset_index()
    )
    monthly["month"] = monthly["month"].astype(str)
    monthly["revenue_growth_pct"] = monthly["revenue"].pct_change().round(4) * 100
    monthly["profit_margin_pct"] = (monthly["profit"] / monthly["revenue"] * 100).round(2)
    return monthly


def top_products(fact_sales: pd.DataFrame, dim_product: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    logger.info("Computing top %s products by revenue", n)
    merged = fact_sales.merge(dim_product, on="product_id", how="left")
    agg = (
        merged.groupby(["product_id", "product_name", "category"])
        .agg(total_revenue=("net_revenue", "sum"), total_profit=("profit", "sum"),
             units_sold=("quantity", "sum"))
        .reset_index()
        .sort_values("total_revenue", ascending=False)
        .head(n)
    )
    return agg


def lowest_margin_products(fact_sales: pd.DataFrame, dim_product: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    logger.info("Computing lowest margin products")
    merged = fact_sales.merge(dim_product, on="product_id", how="left")
    agg = (
        merged.groupby(["product_id", "product_name", "category"])
        .agg(total_revenue=("net_revenue", "sum"), total_profit=("profit", "sum"))
        .reset_index()
    )
    agg["margin_pct"] = (agg["total_profit"] / agg["total_revenue"] * 100).round(2)
    return agg.sort_values("margin_pct", ascending=True).head(n)


def top_customers(fact_sales: pd.DataFrame, dim_customer: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    logger.info("Computing top %s customers by revenue", n)
    merged = fact_sales.merge(dim_customer, on="customer_id", how="left")
    agg = (
        merged.groupby(["customer_id", "customer_name", "segment"])
        .agg(total_revenue=("net_revenue", "sum"), total_orders=("order_id", "nunique"))
        .reset_index()
        .sort_values("total_revenue", ascending=False)
        .head(n)
    )
    return agg


def regional_performance(fact_sales: pd.DataFrame, dim_customer: pd.DataFrame, dim_region: pd.DataFrame) -> pd.DataFrame:
    logger.info("Computing regional performance")
    merged = fact_sales.merge(dim_customer[["customer_id", "region_id"]], on="customer_id", how="left")
    merged = merged.merge(dim_region, on="region_id", how="left")
    merged["region_name"] = merged["region_name"].fillna("Unknown / Unassigned")
    agg = (
        merged.groupby(["region_id", "region_name"], dropna=False)
        .agg(total_revenue=("net_revenue", "sum"), total_profit=("profit", "sum"),
             total_orders=("order_id", "nunique"))
        .reset_index()
    )
    agg["profit_margin_pct"] = (agg["total_profit"] / agg["total_revenue"] * 100).round(2)
    return agg.sort_values("total_revenue", ascending=False)


def customer_growth(dim_customer: pd.DataFrame) -> pd.DataFrame:
    logger.info("Computing customer growth trend")
    growth = (
        dim_customer.assign(signup_month=dim_customer["signup_date"].dt.to_period("M"))
        .groupby("signup_month")
        .size()
        .reset_index(name="new_customers")
    )
    growth["signup_month"] = growth["signup_month"].astype(str)
    growth["cumulative_customers"] = growth["new_customers"].cumsum()
    return growth


def inventory_turnover(fact_sales: pd.DataFrame, dim_inventory: pd.DataFrame) -> pd.DataFrame:
    logger.info("Computing inventory turnover & risk")
    units_sold = fact_sales.groupby("product_id")["quantity"].sum().reset_index(name="units_sold")
    merged = dim_inventory.merge(units_sold, on="product_id", how="left")
    merged["units_sold"] = merged["units_sold"].fillna(0)
    merged["turnover_ratio"] = np.where(
        merged["stock_quantity"] > 0, (merged["units_sold"] / merged["stock_quantity"]).round(2), 0
    )
    merged["risk_flag"] = np.where(merged["needs_reorder"], "REORDER NOW", "OK")
    return merged.sort_values("turnover_ratio", ascending=False)


def main() -> None:
    fact_sales, dim_customer, dim_product, dim_region, dim_inventory = load_processed()

    outputs = {
        "kpi_monthly_sales_growth.csv": monthly_sales_growth(fact_sales),
        "kpi_top_10_products.csv": top_products(fact_sales, dim_product),
        "kpi_lowest_margin_products.csv": lowest_margin_products(fact_sales, dim_product),
        "kpi_top_10_customers.csv": top_customers(fact_sales, dim_customer),
        "kpi_regional_performance.csv": regional_performance(fact_sales, dim_customer, dim_region),
        "kpi_customer_growth.csv": customer_growth(dim_customer),
        "kpi_inventory_turnover.csv": inventory_turnover(fact_sales, dim_inventory),
    }

    for filename, df in outputs.items():
        path = REPORTS_DIR / filename
        df.to_csv(path, index=False)
        logger.info("Wrote %s (%s rows)", path.name, len(df))

    logger.info("All KPI tables written to %s", REPORTS_DIR)


if __name__ == "__main__":
    main()
