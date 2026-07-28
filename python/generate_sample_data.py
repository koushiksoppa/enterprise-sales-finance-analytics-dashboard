"""
generate_sample_data.py
------------------------
Generates a realistic, intentionally-messy raw sales dataset for the
Enterprise Sales & Finance Analytics Dashboard project.

Output (raw, messy on purpose so clean_data.py has real work to do):
    data/raw/customers.csv
    data/raw/products.csv
    data/raw/regions.csv
    data/raw/inventory.csv
    data/raw/sales_transactions.csv

Run:
    python generate_sample_data.py

Author: BI Engineering Team
"""

from __future__ import annotations

import logging
import random
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

REGIONS = [
    ("R01", "North America", "USA"),
    ("R02", "North America", "Canada"),
    ("R03", "Europe", "Germany"),
    ("R04", "Europe", "United Kingdom"),
    ("R05", "Europe", "France"),
    ("R06", "Asia Pacific", "India"),
    ("R07", "Asia Pacific", "Australia"),
    ("R08", "Asia Pacific", "Japan"),
    ("R09", "Latin America", "Brazil"),
    ("R10", "Latin America", "Mexico"),
]

PRODUCT_CATEGORIES = {
    "Electronics": ["Laptop Pro 14", "Wireless Mouse", "4K Monitor", "Mechanical Keyboard", "Noise-Cancel Headphones"],
    "Office Supplies": ["Ergo Office Chair", "Standing Desk", "Desk Lamp", "Whiteboard", "Filing Cabinet"],
    "Software": ["Analytics Suite License", "Cloud Backup Plan", "Security Suite License", "Design Studio License"],
    "Furniture": ["Bookshelf Unit", "Conference Table", "Lounge Sofa", "Storage Cabinet"],
    "Accessories": ["USB-C Hub", "Laptop Sleeve", "Webcam HD", "Portable SSD 1TB"],
}


def generate_regions() -> pd.DataFrame:
    logger.info("Generating region dimension data")
    all_regions = REGIONS + [("R00", "Unknown / Unassigned", "N/A")]
    return pd.DataFrame(all_regions, columns=["region_id", "region_name", "country"])


def generate_customers(n: int = 500) -> pd.DataFrame:
    logger.info("Generating %s customer records", n)
    first_names = ["James", "Mary", "Robert", "Priya", "Wei", "Ahmed", "Sofia", "Lucas",
                   "Emma", "Noah", "Olivia", "Liam", "Ava", "Mohammed", "Chen", "Anya"]
    last_names = ["Smith", "Johnson", "Kumar", "Wang", "Khan", "Silva", "Muller", "Dubois",
                  "Garcia", "Brown", "Wilson", "Tanaka", "Costa", "Rossi", "Novak"]
    segments = ["Enterprise", "SMB", "Consumer", "Government"]

    rows = []
    for i in range(1, n + 1):
        cust_id = f"C{i:05d}"
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        region_id = random.choice(REGIONS)[0]
        segment = random.choices(segments, weights=[0.25, 0.35, 0.30, 0.10])[0]
        signup_date = date(2021, 1, 1) + timedelta(days=random.randint(0, 1400))
        email = f"{name.lower().replace(' ', '.')}{i}@example.com"

        # Intentionally inject messiness for the cleaning script to fix
        if random.random() < 0.03:
            name = None
        if random.random() < 0.02:
            segment = " "
        if random.random() < 0.01:
            region_id = None

        rows.append({
            "customer_id": cust_id,
            "customer_name": name,
            "email": email,
            "segment": segment,
            "region_id": region_id,
            "signup_date": signup_date.isoformat(),
        })

    df = pd.DataFrame(rows)
    dup_sample = df.sample(frac=0.02, random_state=RANDOM_SEED)
    df = pd.concat([df, dup_sample], ignore_index=True)
    return df


def generate_products() -> pd.DataFrame:
    logger.info("Generating product dimension data")
    rows = []
    pid = 1
    for category, items in PRODUCT_CATEGORIES.items():
        for item in items:
            unit_cost = round(random.uniform(15, 800), 2)
            markup = random.uniform(1.3, 2.6)
            unit_price = round(unit_cost * markup, 2)
            rows.append({
                "product_id": f"P{pid:04d}",
                "product_name": item,
                "category": category,
                "unit_cost": unit_cost,
                "unit_price": unit_price,
            })
            pid += 1
    return pd.DataFrame(rows)


def generate_inventory(products: pd.DataFrame) -> pd.DataFrame:
    logger.info("Generating inventory data")
    rows = []
    for _, prod in products.iterrows():
        stock_qty = random.randint(0, 500)
        reorder_level = random.randint(20, 100)
        warehouse = random.choice(["WH-EAST", "WH-WEST", "WH-EU", "WH-APAC"])
        rows.append({
            "product_id": prod["product_id"],
            "warehouse": warehouse,
            "stock_quantity": stock_qty,
            "reorder_level": reorder_level,
            "last_restock_date": (date(2024, 1, 1) + timedelta(days=random.randint(0, 500))).isoformat(),
        })
    return pd.DataFrame(rows)


def generate_sales(customers: pd.DataFrame, products: pd.DataFrame, n: int = 20000) -> pd.DataFrame:
    logger.info("Generating %s sales transaction records", n)
    cust_ids = customers["customer_id"].dropna().unique().tolist()
    prod_ids = products["product_id"].tolist()
    prod_lookup = products.set_index("product_id")[["unit_price", "unit_cost"]].to_dict("index")

    start_date = date(2022, 1, 1)
    end_date = date(2024, 12, 31)
    date_range_days = (end_date - start_date).days

    rows = []
    for i in range(1, n + 1):
        order_id = f"SO{i:06d}"
        cust_id = random.choice(cust_ids)
        prod_id = random.choice(prod_ids)
        order_date = start_date + timedelta(days=random.randint(0, date_range_days))
        quantity = random.randint(1, 12)
        price = prod_lookup[prod_id]["unit_price"]
        cost = prod_lookup[prod_id]["unit_cost"]

        # seasonal boost in Nov/Dec
        if order_date.month in (11, 12):
            quantity = int(quantity * 1.4) + 1

        discount_pct = random.choices([0, 0.05, 0.10, 0.15, 0.20], weights=[0.5, 0.2, 0.15, 0.1, 0.05])[0]
        gross_amount = round(price * quantity, 2)
        discount_amount = round(gross_amount * discount_pct, 2)
        net_revenue = round(gross_amount - discount_amount, 2)
        total_cost = round(cost * quantity, 2)

        # inject messiness
        qty_val = quantity
        if random.random() < 0.015:
            qty_val = -1  # invalid quantity
        if random.random() < 0.01:
            net_revenue = None  # missing revenue

        rows.append({
            "order_id": order_id,
            "order_date": order_date.isoformat(),
            "customer_id": cust_id,
            "product_id": prod_id,
            "quantity": qty_val,
            "unit_price": price,
            "discount_pct": discount_pct,
            "gross_amount": gross_amount,
            "discount_amount": discount_amount,
            "net_revenue": net_revenue,
            "total_cost": total_cost,
        })

    df = pd.DataFrame(rows)
    dup_sample = df.sample(frac=0.01, random_state=RANDOM_SEED)
    df = pd.concat([df, dup_sample], ignore_index=True)
    return df


def main() -> None:
    regions = generate_regions()
    customers = generate_customers()
    products = generate_products()
    inventory = generate_inventory(products)
    sales = generate_sales(customers, products)

    regions.to_csv(RAW_DIR / "regions.csv", index=False)
    customers.to_csv(RAW_DIR / "customers.csv", index=False)
    products.to_csv(RAW_DIR / "products.csv", index=False)
    inventory.to_csv(RAW_DIR / "inventory.csv", index=False)
    sales.to_csv(RAW_DIR / "sales_transactions.csv", index=False)

    logger.info("Raw sample data generated in: %s", RAW_DIR)
    logger.info("Files: regions.csv, customers.csv, products.csv, inventory.csv, sales_transactions.csv")


if __name__ == "__main__":
    main()
