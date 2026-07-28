"""
generate_insights.py
---------------------
Reads the KPI tables from reports/ (produced by build_kpis.py) and writes
a plain-English executive insights report to reports/executive_insights.md.

Run:
    python generate_insights.py
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"


def main() -> None:
    regional = pd.read_csv(REPORTS_DIR / "kpi_regional_performance.csv")
    top_products = pd.read_csv(REPORTS_DIR / "kpi_top_10_products.csv")
    low_margin = pd.read_csv(REPORTS_DIR / "kpi_lowest_margin_products.csv")
    growth = pd.read_csv(REPORTS_DIR / "kpi_customer_growth.csv")
    inventory = pd.read_csv(REPORTS_DIR / "kpi_inventory_turnover.csv")
    monthly = pd.read_csv(REPORTS_DIR / "kpi_monthly_sales_growth.csv")

    best_region = regional.iloc[0]
    worst_region = regional.iloc[-1]
    best_product = top_products.iloc[0]
    worst_margin_product = low_margin.iloc[0]
    reorder_risk = inventory[inventory["risk_flag"] == "REORDER NOW"]
    latest_growth_pct = monthly["revenue_growth_pct"].dropna().iloc[-1] if monthly["revenue_growth_pct"].notna().any() else 0
    total_new_customers = growth["new_customers"].sum()

    lines = [
        "# Executive Business Insights",
        "",
        f"_Auto-generated from `reports/` KPI tables._",
        "",
        "## Regional Performance",
        f"- **Best performing region:** {best_region['region_name']} — "
        f"${best_region['total_revenue']:,.0f} revenue, "
        f"{best_region['profit_margin_pct']:.1f}% profit margin.",
        f"- **Worst performing region:** {worst_region['region_name']} — "
        f"${worst_region['total_revenue']:,.0f} revenue, "
        f"{worst_region['profit_margin_pct']:.1f}% profit margin. "
        "Recommend a regional sales review and targeted promotions.",
        "",
        "## Product Performance",
        f"- **Most profitable product:** {best_product['product_name']} "
        f"({best_product['category']}) — ${best_product['total_revenue']:,.0f} in revenue.",
        f"- **Lowest margin product:** {worst_margin_product['product_name']} "
        f"({worst_margin_product['category']}) at {worst_margin_product['margin_pct']:.1f}% margin. "
        "Consider renegotiating supplier cost or repricing.",
        "",
        "## Customer Growth",
        f"- Total new customers acquired over the observed period: {total_new_customers:,.0f}.",
        f"- Most recent month-over-month revenue growth: {latest_growth_pct:.1f}%.",
        "",
        "## Inventory Risk",
        f"- {len(reorder_risk)} product(s) are at or below reorder level and need immediate restocking:",
    ]
    for _, row in reorder_risk.iterrows():
        lines.append(f"  - {row['product_id']} in {row['warehouse']} "
                      f"(stock: {row['stock_quantity']}, reorder level: {row['reorder_level']})")
    if reorder_risk.empty:
        lines.append("  - None — inventory levels are currently healthy across all warehouses.")

    lines += [
        "",
        "## Executive Recommendations",
        f"1. Reinforce marketing spend and account coverage in {best_region['region_name']} "
        "to compound its lead, while running a root-cause review in "
        f"{worst_region['region_name']} (pricing, logistics, or demand mix).",
        f"2. Reprice or bundle {worst_margin_product['product_name']} — its margin is dragging "
        "portfolio profitability relative to top performers.",
        "3. Prioritize restocking for the flagged inventory items above to avoid stockout-driven "
        "revenue loss in the next order cycle.",
        "4. Expand acquisition channels that are driving new customer growth; monitor the "
        "Customer Growth trend on the Customer Analytics dashboard page monthly.",
    ]

    out_path = REPORTS_DIR / "executive_insights.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Executive insights written to %s", out_path)


if __name__ == "__main__":
    main()
