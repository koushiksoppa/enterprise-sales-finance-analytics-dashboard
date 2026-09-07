"""
clean_data.py
--------------
ETL pipeline: loads raw CSVs, cleans them, engineers features, and writes
star-schema-ready dimension/fact tables to data/processed/ for Power BI
and SQL loading.

Run:
    python clean_data.py
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Tuple

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def load_raw() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    logger.info("Loading raw CSV files from %s", RAW_DIR)
    regions = pd.read_csv(RAW_DIR / "regions.csv")
    customers = pd.read_csv(RAW_DIR / "customers.csv")
    products = pd.read_csv(RAW_DIR / "products.csv")
    inventory = pd.read_csv(RAW_DIR / "inventory.csv")
    sales = pd.read_csv(RAW_DIR / "sales_transactions.csv")
    return regions, customers, products, inventory, sales


def clean_customers(df: pd.DataFrame, valid_region_ids: set) -> pd.DataFrame:
    logger.info("Cleaning customer data: %s raw rows", len(df))
    df = df.drop_duplicates(subset=["customer_id"]).copy()

    df["customer_name"] = df["customer_name"].fillna("Unknown Customer")
    df["segment"] = df["segment"].astype(str).str.strip()
    df.loc[df["segment"].isin(["", "nan", "None"]), "segment"] = "Unclassified"

    df["region_id"] = df["region_id"].where(df["region_id"].isin(valid_region_ids), other=np.nan)
    df["region_id"] = df["region_id"].fillna("R00")  # Unknown region bucket

    df["signup_date"] = pd.to_datetime(df["signup_date"], errors="coerce")
    df["signup_date"] = df["signup_date"].fillna(pd.Timestamp("2021-01-01"))

    logger.info("Customer data cleaned: %s rows remain", len(df))
    return df.reset_index(drop=True)


def clean_products(df: pd.DataFrame) -> pd.DataFrame:
    logger.info("Cleaning product data: %s raw rows", len(df))
    df = df.drop_duplicates(subset=["product_id"]).copy()
    df["unit_cost"] = pd.to_numeric(df["unit_cost"], errors="coerce")
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")
    df = df.dropna(subset=["unit_cost", "unit_price"])
    df["margin_pct"] = ((df["unit_price"] - df["unit_cost"]) / df["unit_price"]).round(4)
    return df.reset_index(drop=True)


def clean_inventory(df: pd.DataFrame, valid_product_ids: set) -> pd.DataFrame:
    logger.info("Cleaning inventory data: %s raw rows", len(df))
    df = df[df["product_id"].isin(valid_product_ids)].copy()
    df["stock_quantity"] = pd.to_numeric(df["stock_quantity"], errors="coerce").fillna(0).astype(int)
    df["reorder_level"] = pd.to_numeric(df["reorder_level"], errors="coerce").fillna(0).astype(int)
    df["last_restock_date"] = pd.to_datetime(df["last_restock_date"], errors="coerce")
    df["needs_reorder"] = df["stock_quantity"] <= df["reorder_level"]
    return df.reset_index(drop=True)


def clean_sales(df: pd.DataFrame, valid_cust_ids: set, valid_prod_ids: set) -> pd.DataFrame:
    logger.info("Cleaning sales data: %s raw rows", len(df))
    df = df.drop_duplicates(subset=["order_id"]).copy()

    df = df[df["customer_id"].isin(valid_cust_ids)]
    df = df[df["product_id"].isin(valid_prod_ids)]

    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df = df[df["quantity"] > 0]  # drop invalid/negative quantities

    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    df = df.dropna(subset=["order_date"])

    df["net_revenue"] = pd.to_numeric(df["net_revenue"], errors="coerce")
    # recompute missing net_revenue from gross - discount
    recompute_mask = df["net_revenue"].isna()
    df.loc[recompute_mask, "net_revenue"] = (
        df.loc[recompute_mask, "gross_amount"] - df.loc[recompute_mask, "discount_amount"]
    )

    df["total_cost"] = pd.to_numeric(df["total_cost"], errors="coerce").fillna(0)
    df["profit"] = (df["net_revenue"] - df["total_cost"]).round(2)
    df["profit_margin_pct"] = np.where(
        df["net_revenue"] > 0, (df["profit"] / df["net_revenue"]).round(4), 0
    )

    logger.info("Sales data cleaned: %s rows remain", len(df))
    return df.reset_index(drop=True)


def build_date_dim(sales: pd.DataFrame) -> pd.DataFrame:
    logger.info("Building DimDate")
    start = sales["order_date"].min()
    end = sales["order_date"].max()
    date_range = pd.date_range(start=start.normalize(), end=end.normalize(), freq="D")
    dim = pd.DataFrame({"date": date_range})
    dim["date_id"] = dim["date"].dt.strftime("%Y%m%d").astype(int)
    dim["year"] = dim["date"].dt.year
    dim["quarter"] = dim["date"].dt.quarter
    dim["month"] = dim["date"].dt.month
    dim["month_name"] = dim["date"].dt.strftime("%B")
    dim["day"] = dim["date"].dt.day
    dim["day_name"] = dim["date"].dt.strftime("%A")
    dim["week_of_year"] = dim["date"].dt.isocalendar().week.astype(int)
    dim["is_weekend"] = dim["date"].dt.dayofweek >= 5
    dim["fiscal_year"] = np.where(dim["month"] >= 4, dim["year"], dim["year"] - 1)
    return dim[["date_id", "date", "year", "quarter", "month", "month_name",
                "day", "day_name", "week_of_year", "is_weekend", "fiscal_year"]]


def build_kpi_summary(fact_sales: pd.DataFrame, customers: pd.DataFrame, regions: pd.DataFrame) -> pd.DataFrame:
    """A region-grain summary written alongside the star schema.

    Grouped on region_name, not region_id: DimRegion is at country grain, so
    region_name repeats and grouping by id would split one region into several.
    The richer version of this table is reports/kpi_regional_performance.csv.
    """
    logger.info("Building KPI summary table")
    merged = fact_sales.merge(customers[["customer_id", "region_id"]], on="customer_id", how="left")
    merged = merged.merge(regions[["region_id", "region_name"]], on="region_id", how="left")
    merged["region_name"] = merged["region_name"].fillna("Unknown / Unassigned")

    summary = (
        merged.groupby("region_name", dropna=False)
        .agg(
            total_revenue=("net_revenue", "sum"),
            total_profit=("profit", "sum"),
            total_orders=("order_id", "nunique"),
            avg_order_value=("net_revenue", "mean"),
        )
        .reset_index()
    )
    summary["total_revenue"] = summary["total_revenue"].round(2)
    summary["total_profit"] = summary["total_profit"].round(2)
    summary["avg_order_value"] = summary["avg_order_value"].round(2)
    summary["profit_margin_pct"] = (summary["total_profit"] / summary["total_revenue"]).round(4)
    summary = summary.sort_values("total_revenue", ascending=False).reset_index(drop=True)
    return summary


def main() -> None:
    regions, customers_raw, products_raw, inventory_raw, sales_raw = load_raw()

    valid_region_ids = set(regions["region_id"])
    dim_customer = clean_customers(customers_raw, valid_region_ids)

    dim_product = clean_products(products_raw)
    valid_product_ids = set(dim_product["product_id"])

    dim_inventory = clean_inventory(inventory_raw, valid_product_ids)

    valid_cust_ids = set(dim_customer["customer_id"])
    fact_sales = clean_sales(sales_raw, valid_cust_ids, valid_product_ids)

    dim_date = build_date_dim(fact_sales)

    # add date_id foreign key to fact table for star-schema join
    fact_sales["date_id"] = fact_sales["order_date"].dt.strftime("%Y%m%d").astype(int)

    kpi_summary = build_kpi_summary(fact_sales, dim_customer, regions)

    # Write outputs
    regions.to_csv(PROCESSED_DIR / "DimRegion.csv", index=False)
    dim_customer.to_csv(PROCESSED_DIR / "DimCustomer.csv", index=False)
    dim_product.to_csv(PROCESSED_DIR / "DimProduct.csv", index=False)
    dim_inventory.to_csv(PROCESSED_DIR / "DimInventory.csv", index=False)
    dim_date.to_csv(PROCESSED_DIR / "DimDate.csv", index=False)
    fact_sales.to_csv(PROCESSED_DIR / "FactSales.csv", index=False)
    kpi_summary.to_csv(PROCESSED_DIR / "KPI_RegionSummary.csv", index=False)

    logger.info("ETL complete. Star-schema CSVs written to %s", PROCESSED_DIR)
    logger.info("FactSales rows: %s | DimCustomer: %s | DimProduct: %s | DimDate: %s",
                len(fact_sales), len(dim_customer), len(dim_product), len(dim_date))


if __name__ == "__main__":
    main()
