"""
prepare_sql_csv.py
-------------------
Takes the analytics-friendly CSVs in data/processed/ (produced by
clean_data.py) and writes SQL-Server-ready versions with column order
and data types matching sql/01_schema.sql exactly, for use with
sql/02_load_data.sql (BULK INSERT).

Run:
    python prepare_sql_csv.py
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"


def prepare_inventory() -> None:
    df = pd.read_csv(PROCESSED_DIR / "DimInventory.csv")
    df = df[["product_id", "warehouse", "stock_quantity", "reorder_level",
             "last_restock_date", "needs_reorder"]]
    df["needs_reorder"] = df["needs_reorder"].astype(int)
    out = PROCESSED_DIR / "DimInventory_ForSql.csv"
    df.to_csv(out, index=False)
    logger.info("Wrote %s (%s rows)", out.name, len(df))


def prepare_fact_sales() -> None:
    df = pd.read_csv(PROCESSED_DIR / "FactSales.csv")
    df = df[["order_id", "date_id", "customer_id", "product_id", "quantity",
             "unit_price", "discount_pct", "gross_amount", "discount_amount",
             "net_revenue", "total_cost", "profit", "profit_margin_pct"]]
    out = PROCESSED_DIR / "FactSales_ForSql.csv"
    df.to_csv(out, index=False)
    logger.info("Wrote %s (%s rows)", out.name, len(df))


def prepare_date_dim() -> None:
    df = pd.read_csv(PROCESSED_DIR / "DimDate.csv")
    df = df.rename(columns={"date": "full_date"})
    df["is_weekend"] = df["is_weekend"].astype(int)
    df = df[["date_id", "full_date", "year", "quarter", "month", "month_name",
             "day", "day_name", "week_of_year", "is_weekend", "fiscal_year"]]
    df.to_csv(PROCESSED_DIR / "DimDate.csv", index=False)
    logger.info("Normalized DimDate.csv column order for SQL load")


def main() -> None:
    prepare_date_dim()
    prepare_inventory()
    prepare_fact_sales()
    logger.info("SQL-ready CSVs generated in %s", PROCESSED_DIR)


if __name__ == "__main__":
    main()
