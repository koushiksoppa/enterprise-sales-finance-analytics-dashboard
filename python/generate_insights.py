"""
generate_insights.py
---------------------
Reads the KPI tables from reports/ (produced by build_kpis.py) and writes the
executive insights report in two formats from one set of findings, so the two
can never disagree:

    reports/executive_insights.md    - version-control friendly
    reports/executive_insights.html  - styled, print-ready briefing

Every figure quoted below is read from a KPI table. Nothing is estimated or
hand-written, and the recommendation list is derived from the same findings
rather than authored separately.

Run:
    python generate_insights.py
"""

from __future__ import annotations

import html
import logging
from datetime import date
from pathlib import Path

import pandas as pd

import report_theme as t

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"

REPORT_TITLE = "Executive Business Review"
REPORT_SUBTITLE = "Sales, profitability, customer and inventory performance"

# Two buckets in the dimensions hold rows that failed a data-quality check
# rather than describing a real market or segment: customers whose source
# region_id was invalid, and customers whose segment arrived blank. Both are
# shown in the detail tables but excluded from rankings and recommendations,
# because "grow the Unclassified segment" is a reporting artefact, not advice.
UNKNOWN_REGION = "Unknown / Unassigned"
UNCLASSIFIED_SEGMENT = "Unclassified"

# A segment mix shift is only worth recommending when the segments actually
# differ; below this spread in revenue per customer the ranking is noise.
MATERIAL_SPREAD_PCT = 15.0


# ------------------------------------------------------------------- input --

def load_kpis() -> dict:
    logger.info("Loading KPI tables from %s", REPORTS_DIR)
    names = [
        "executive_summary", "monthly_sales_growth", "top_10_products",
        "lowest_margin_products", "top_10_customers", "regional_performance",
        "country_performance", "category_performance", "segment_performance",
        "customer_growth", "inventory_turnover", "revenue_forecast",
    ]
    return {name: pd.read_csv(REPORTS_DIR / f"kpi_{name}.csv") for name in names}


def summary_values(summary: pd.DataFrame) -> dict:
    """kpi_executive_summary.csv as {metric: (value, format)}."""
    return {row["metric"]: (row["value"], row["format"]) for _, row in summary.iterrows()}


# ---------------------------------------------------------------- analysis --

def build_findings(kpi: dict) -> dict:
    """Derive every statement the report makes, once, from the KPI tables."""
    logger.info("Deriving findings")
    summary = summary_values(kpi["executive_summary"])
    monthly = kpi["monthly_sales_growth"]
    regional = kpi["regional_performance"]
    categories = kpi["category_performance"]
    segments = kpi["segment_performance"]
    products = kpi["top_10_products"]
    low_margin = kpi["lowest_margin_products"]
    customers = kpi["top_10_customers"]
    inventory = kpi["inventory_turnover"]
    forecast = kpi["revenue_forecast"]
    growth = kpi["customer_growth"]

    real_regions = regional[regional["region_name"] != UNKNOWN_REGION]
    unassigned = regional[regional["region_name"] == UNKNOWN_REGION]
    real_segments = segments[segments["segment"] != UNCLASSIFIED_SEGMENT]
    unclassified = segments[segments["segment"] == UNCLASSIFIED_SEGMENT]

    by_margin = real_regions.sort_values("profit_margin_pct", ascending=False)
    best_product_revenue = products.iloc[0]
    best_product_profit = products.sort_values("total_profit", ascending=False).iloc[0]

    reorder_now = inventory[inventory["risk_flag"] == "REORDER NOW"]
    at_risk = inventory[inventory["risk_flag"] == "AT RISK"]

    future = forecast[forecast["is_forecast"] == 1]
    history = forecast[forecast["is_forecast"] == 0]
    # Compare the projection with the SAME calendar months a year earlier, not
    # with the trailing months. The trailing window ends on the November/December
    # peak, so a trailing comparison would read a seasonal step-down as decline.
    baseline_index = set(future["month_index"] - 12)
    baseline = history[history["month_index"].isin(baseline_index)]

    return {
        "summary": summary,
        "period_start": t.month_label(monthly.iloc[0]["month"]),
        "period_end": t.month_label(monthly.iloc[-1]["month"]),
        "months_observed": len(monthly),

        "regions": real_regions,
        "best_region": real_regions.iloc[0],
        "weakest_region": real_regions.iloc[-1],
        "best_margin_region": by_margin.iloc[0],
        "worst_margin_region": by_margin.iloc[-1],
        "unassigned_revenue": float(unassigned["total_revenue"].sum()),
        "unassigned_share": float(unassigned["revenue_share_pct"].sum()),
        "unassigned_orders": int(unassigned["total_orders"].sum()),
        "unclassified_customers": int(unclassified["total_customers"].sum()),
        "unclassified_share": float(unclassified["revenue_share_pct"].sum()),

        "categories": categories,
        "best_category": categories.iloc[0],
        "worst_margin_category": categories.sort_values("profit_margin_pct").iloc[0],

        "top_products": products,
        "best_product_revenue": best_product_revenue,
        "best_product_profit": best_product_profit,
        "low_margin": low_margin,
        "worst_margin_product": low_margin.iloc[0],

        "segments": segments,
        "real_segments": real_segments,
        "top_segment": real_segments.iloc[0],
        "top_customers": customers,
        "top10_revenue_share": float(
            customers["total_revenue"].sum() / summary["Total Revenue"][0] * 100),
        "signup_first": growth.iloc[0]["signup_month"],
        "signup_last": growth.iloc[-1]["signup_month"],
        "customers_on_file": int(summary["Customers On File"][0]),

        "inventory": inventory,
        "reorder_now": reorder_now,
        "at_risk": at_risk,
        "stock_value": float(inventory["stock_value"].sum()),
        "reorder_stock_value": float(reorder_now["stock_value"].sum()),

        "monthly": monthly,
        "forecast": forecast,
        "forecast_months": future,
        "forecast_total": float(future["forecast_revenue"].sum()),
        "forecast_lower_total": float(future["forecast_lower"].sum()),
        "forecast_upper_total": float(future["forecast_upper"].sum()),
        "baseline_total": float(baseline["actual_revenue"].sum()),
        "baseline_label": (t.month_label(baseline.iloc[0]["month"]) + " to "
                           + t.month_label(baseline.iloc[-1]["month"])),
        "forecast_label": (t.month_label(future.iloc[0]["month"]) + " to "
                           + t.month_label(future.iloc[-1]["month"])),
        "forecast_vs_baseline_pct": float(
            future["forecast_revenue"].sum() / baseline["actual_revenue"].sum() * 100 - 100),
        "forecast_horizon": len(future),
    }


def build_recommendations(f: dict) -> list[str]:
    """Recommendations are assembled from the findings above, in priority order.

    The wording branches on what the data actually shows - a saturated repeat
    rate and a diversified revenue base call for different actions than a
    concentrated one, and asserting the wrong one would be a fabricated finding.
    """
    recs: list[str] = []
    blended_margin = f["summary"]["Profit Margin %"][0]
    worst_category = f["worst_margin_category"]
    margin_gap = blended_margin - worst_category["profit_margin_pct"]

    recs.append(
        f"Address the margin gap in {worst_category['category']}: "
        f"{t.percent(worst_category['profit_margin_pct'])} margin on "
        f"{t.money_compact(worst_category['total_revenue'])} of revenue, "
        f"{margin_gap:.1f} points below the {t.percent(blended_margin)} blended margin. It is the "
        f"weakest category and the largest structural drag on portfolio profitability."
    )
    recs.append(
        f"Reprice or renegotiate supply for {f['worst_margin_product']['product_name']} "
        f"({t.percent(f['worst_margin_product']['margin_pct'])} margin). It carries "
        f"{t.money_compact(f['worst_margin_product']['total_revenue'])} of revenue, so a margin "
        f"correction here moves the portfolio, not just the line item."
    )
    recs.append(
        f"Fund coverage in {f['best_region']['region_name']}, which already contributes "
        f"{t.percent(f['best_region']['revenue_share_pct'])} of revenue at "
        f"{t.percent(f['best_region']['profit_margin_pct'])} margin, and run a commercial review "
        f"in {f['weakest_region']['region_name']} "
        f"({t.percent(f['weakest_region']['revenue_share_pct'])} share)."
    )

    if len(f["reorder_now"]) > 0:
        names = ", ".join(f["reorder_now"]["product_name"].tolist())
        recs.append(
            f"Raise replenishment orders for {len(f['reorder_now'])} product(s) now at or below "
            f"the reorder trigger ({names}) before the next order cycle converts the shortfall "
            f"into lost revenue."
        )
    elif len(f["at_risk"]) > 0:
        recs.append(
            f"Bring forward replenishment planning for {len(f['at_risk'])} product(s) within 25% "
            f"of the reorder trigger; none has breached it yet, but the buffer is thin."
        )

    repeat_rate = f["summary"]["Repeat Customer Rate %"][0]
    concentration = f["top10_revenue_share"]
    top_segment = f["top_segment"]

    by_value = f["real_segments"].sort_values("revenue_per_customer", ascending=False)
    richest, leanest = by_value.iloc[0], by_value.iloc[-1]
    segment_spread = richest["revenue_per_customer"] / leanest["revenue_per_customer"] * 100 - 100

    if repeat_rate >= 90 and concentration < 10:
        # Every customer already reorders and no account dominates, so neither
        # retention nor de-risking is the lever. Which lever *is* available
        # depends on whether the segments meaningfully differ.
        if segment_spread >= MATERIAL_SPREAD_PCT:
            recs.append(
                f"Retention is not the constraint - {t.percent(repeat_rate)} of customers already "
                f"reorder and the top 10 accounts hold only {t.percent(concentration)} of revenue. "
                f"Shift acquisition and cross-sell toward {richest['segment']}, which returns "
                f"{t.money_compact(richest['revenue_per_customer'])} per customer against "
                f"{t.money_compact(leanest['revenue_per_customer'])} in {leanest['segment']} "
                f"({segment_spread:.0f}% higher), to raise revenue without adding accounts."
            )
        else:
            best_mix = f["categories"].sort_values("profit_margin_pct", ascending=False).iloc[0]
            widest_aov = f["categories"].sort_values("avg_order_value", ascending=False).iloc[0]
            recs.append(
                f"Retention is not the constraint - {t.percent(repeat_rate)} of customers already "
                f"reorder, the top 10 accounts hold only {t.percent(concentration)} of revenue, "
                f"and revenue per customer varies by just {segment_spread:.0f}% across segments. "
                f"The material lever is product mix, not customer mix: "
                f"{widest_aov['category']} carries a "
                f"{t.money(widest_aov['avg_order_value'])} average order against "
                f"{t.money(f['categories'].sort_values('avg_order_value').iloc[0]['avg_order_value'])} "
                f"in {f['categories'].sort_values('avg_order_value').iloc[0]['category']}, and "
                f"{best_mix['category']} is the highest-margin category at "
                f"{t.percent(best_mix['profit_margin_pct'])}."
            )
    elif concentration >= 25:
        recs.append(
            f"Reduce concentration risk: the top 10 accounts hold "
            f"{t.percent(concentration)} of revenue. Build coverage depth beneath them, starting "
            f"in {top_segment['segment']}, the largest segment by revenue."
        )
    else:
        recs.append(
            f"Lift the repeat rate from {t.percent(repeat_rate)}. Re-order programmes aimed at "
            f"{top_segment['segment']}, the largest segment by revenue "
            f"({t.percent(top_segment['repeat_customer_rate_pct'])} repeat rate), convert "
            f"one-time buyers without new acquisition spend."
        )
    return recs


# ------------------------------------------------------------- rendering ----

HEADLINE_METRICS = [
    "Total Revenue", "Total Profit", "Profit Margin %", "Revenue Growth YoY %",
    "Total Orders", "Average Order Value", "Total Customers", "Repeat Customer Rate %",
]


def render_markdown(f: dict) -> str:
    s = f["summary"]
    lines: list[str] = [
        f"# {REPORT_TITLE}",
        "",
        f"**{REPORT_SUBTITLE}**  ",
        f"Reporting period: {f['period_start']} to {f['period_end']} "
        f"({f['months_observed']} months) · Generated {date.today().isoformat()}",
        "",
        "> Figures are computed directly from the KPI tables in `reports/` by "
        "`python/build_kpis.py`. Definitions for every metric are in "
        "`docs/KPI_DEFINITIONS.md`.",
        "",
        "## Performance at a glance",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for metric in HEADLINE_METRICS:
        value, fmt = s[metric]
        rendered = t.signed_percent(value) if "Growth" in metric else t.format_value(value, fmt)
        lines.append(f"| {metric} | {rendered} |")

    lines += [
        "",
        "## Where the business is growing",
        "",
        f"- **Strongest region:** {f['best_region']['region_name']} — "
        f"{t.money(f['best_region']['total_revenue'])} revenue "
        f"({t.percent(f['best_region']['revenue_share_pct'])} of the total) at "
        f"{t.percent(f['best_region']['profit_margin_pct'])} margin, across "
        f"{int(f['best_region']['countries'])} countries.",
        f"- **Weakest region by revenue:** {f['weakest_region']['region_name']} — "
        f"{t.money(f['weakest_region']['total_revenue'])} "
        f"({t.percent(f['weakest_region']['revenue_share_pct'])} of the total) at "
        f"{t.percent(f['weakest_region']['profit_margin_pct'])} margin.",
        f"- **Margin spread across regions** is narrow: "
        f"{t.percent(f['worst_margin_region']['profit_margin_pct'])} "
        f"({f['worst_margin_region']['region_name']}) to "
        f"{t.percent(f['best_margin_region']['profit_margin_pct'])} "
        f"({f['best_margin_region']['region_name']}), so revenue mix — not regional pricing — "
        f"drives the profit differences.",
        f"- **Largest category:** {f['best_category']['category']} — "
        f"{t.money(f['best_category']['total_revenue'])} "
        f"({t.percent(f['best_category']['revenue_share_pct'])} of revenue) at "
        f"{t.percent(f['best_category']['profit_margin_pct'])} margin.",
        "",
        "## Profitability",
        "",
        f"- **Highest revenue product:** {f['best_product_revenue']['product_name']} "
        f"({f['best_product_revenue']['category']}) — "
        f"{t.money(f['best_product_revenue']['total_revenue'])} revenue, "
        f"{t.percent(f['best_product_revenue']['profit_margin_pct'])} margin.",
        f"- **Highest profit product:** {f['best_product_profit']['product_name']} "
        f"({f['best_product_profit']['category']}) — "
        f"{t.money(f['best_product_profit']['total_profit'])} profit.",
        f"- **Lowest margin product:** {f['worst_margin_product']['product_name']} "
        f"({f['worst_margin_product']['category']}) at "
        f"{t.percent(f['worst_margin_product']['margin_pct'])} — status "
        f"*{t.margin_status(f['worst_margin_product']['margin_pct'])}* against the "
        f"{t.percent(t.MARGIN_HEALTHY)} / {t.percent(t.MARGIN_WATCH)} margin bands.",
        f"- **Weakest category by margin:** {f['worst_margin_category']['category']} at "
        f"{t.percent(f['worst_margin_category']['profit_margin_pct'])}.",
        "",
        "## Customers",
        "",
        f"- {t.number(s['Total Customers'][0])} customers placed at least one order; "
        f"{t.number(f['customers_on_file'])} are on file in total.",
        f"- **Repeat customer rate:** {t.percent(s['Repeat Customer Rate %'][0])} of transacting "
        f"customers ordered more than once"
        + (", so the metric is saturated on this customer base and carries no signal - "
           "average orders per customer is the more informative depth measure here."
           if s["Repeat Customer Rate %"][0] >= 99 else "."),
        f"- **Orders per customer:** "
        f"{s['Total Orders'][0] / s['Total Customers'][0]:,.1f} on average across the period.",
        f"- **Revenue concentration:** the top 10 customers hold "
        f"{t.percent(f['top10_revenue_share'])} of total revenue"
        + (" - revenue is broadly distributed, so no single account is a material dependency."
           if f["top10_revenue_share"] < 10 else "."),
        f"- **Largest segment:** {f['top_segment']['segment']} — "
        f"{t.money(f['top_segment']['total_revenue'])} "
        f"({t.percent(f['top_segment']['revenue_share_pct'])} of revenue) from "
        f"{t.number(f['top_segment']['total_customers'])} customers, "
        f"{t.money(f['top_segment']['revenue_per_customer'])} each.",
        f"- Acquisition is measured from customer signup dates, which run "
        f"{f['signup_first']} to {f['signup_last']} — a wider window than the sales period.",
        "",
        "## Inventory risk",
        "",
        f"- **Stock on hand:** {t.money(f['stock_value'])} at cost across "
        f"{len(f['inventory'])} product/warehouse positions.",
        f"- **Inventory turnover:** {t.ratio(s['Inventory Turnover Ratio'][0])} — units sold over "
        f"the full {f['months_observed']}-month period against a point-in-time stock snapshot, so "
        f"it measures relative velocity between products rather than an annualised turn rate.",
    ]

    if len(f["reorder_now"]) > 0:
        lines.append(f"- **At or below reorder level:** {len(f['reorder_now'])} product(s).")
        for _, row in f["reorder_now"].iterrows():
            lines.append(
                f"  - {row['product_name']} ({row['product_id']}) in {row['warehouse']} — "
                f"stock {int(row['stock_quantity'])} vs reorder level "
                f"{int(row['reorder_level'])}"
            )
    else:
        lines.append("- **At or below reorder level:** none.")
    lines.append(
        f"- **Within 25% of the reorder trigger:** {len(f['at_risk'])} product(s)."
    )

    lines += [
        "",
        "## Outlook",
        "",
        f"- A seasonal linear-trend model projects {t.money(f['forecast_total'])} of revenue for "
        f"{f['forecast_label']}, within a modelled range of "
        f"{t.money(f['forecast_lower_total'])} to {t.money(f['forecast_upper_total'])}.",
        f"- That is {t.signed_percent(f['forecast_vs_baseline_pct'])} against the same months a "
        f"year earlier ({f['baseline_label']}: {t.money(f['baseline_total'])}). The comparison is "
        f"year-on-year rather than against the trailing six months, which end on the "
        f"November/December peak and would read a normal seasonal step-down as decline.",
        "- The projection extrapolates the observed trend and month-of-year seasonality. It is a "
        "planning input, not a commitment, and it assumes no change in pricing, product mix, or "
        "market conditions.",
        "",
        "## Recommendations",
        "",
    ]
    for i, rec in enumerate(build_recommendations(f), start=1):
        lines.append(f"{i}. {rec}")

    lines += [
        "",
        "## Data quality note",
        "",
        f"- {t.money(f['unassigned_revenue'])} of revenue "
        f"({t.percent(f['unassigned_share'])}, {t.number(f['unassigned_orders'])} orders) belongs "
        f"to customers whose source `region_id` failed referential integrity. The ETL preserves "
        f"the revenue in an *{UNKNOWN_REGION}* bucket rather than dropping it, and regional "
        f"rankings above exclude the bucket so a data-quality artefact is never reported as a "
        f"market finding.",
        f"- {t.number(f['unclassified_customers'])} customers "
        f"({t.percent(f['unclassified_share'])} of revenue) arrived with a blank segment and sit "
        f"in an *{UNCLASSIFIED_SEGMENT}* bucket. They appear in the segment table but are excluded "
        f"from segment rankings for the same reason.",
        "- Region rankings roll countries up to their region. `DimRegion` is at country grain, so "
        "grouping by `region_id` would split one region into several.",
        "",
    ]
    return "\n".join(lines)


def _kpi_cards_html(f: dict) -> str:
    s = f["summary"]
    cards = []
    for metric in HEADLINE_METRICS:
        value, fmt = s[metric]
        is_growth = "Growth" in metric
        display = t.signed_percent(value) if is_growth else t.format_value_compact(value, fmt)
        colour = t.sentiment_color(value) if is_growth else t.INK
        definition = next(
            (r["definition"] for _, r in f["summary_frame"].iterrows() if r["metric"] == metric), ""
        )
        cards.append(
            f'<div class="card"><div class="card-label">{html.escape(metric)}</div>'
            f'<div class="card-value" style="color:{colour}">{html.escape(display)}</div>'
            f'<div class="card-note">{html.escape(definition)}</div></div>'
        )
    return '<div class="cards">' + "".join(cards) + "</div>"


def _table_html(df: pd.DataFrame, columns: list[tuple[str, str, str]]) -> str:
    """Render a table. `columns` is a list of (source column, header, format)."""
    head = "".join(
        f'<th class="{"num" if fmt != "text" else ""}">{html.escape(header)}</th>'
        for _, header, fmt in columns
    )
    formatters = {
        "text": lambda v: html.escape(str(v)),
        "money": t.money,
        "money_compact": t.money_compact,
        "percent": t.percent,
        "number": t.number,
        "ratio": t.ratio,
    }
    body = []
    for _, row in df.iterrows():
        cells = []
        for source, _, fmt in columns:
            rendered = formatters[fmt](row[source])
            css = "" if fmt == "text" else ' class="num"'
            cells.append(f"<td{css}>{html.escape(str(rendered))}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (
        '<div class="table-wrap"><table><thead><tr>' + head + "</tr></thead><tbody>"
        + "".join(body) + "</tbody></table></div>"
    )


def _customer_caveat_html(f: dict) -> str:
    """Flag the metrics that carry no signal on this customer base, rather than
    presenting a saturated value as a business result."""
    notes = []
    if f["summary"]["Repeat Customer Rate %"][0] >= 99:
        notes.append(
            "Every transacting customer has ordered more than once, so the repeat rate is "
            "saturated and carries no signal here - read average orders per customer instead."
        )
    if f["top10_revenue_share"] < 10:
        notes.append(
            "Revenue is broadly distributed across the base, so no single account is a material "
            "dependency."
        )
    if not notes:
        return ""
    return ('<p class="callout method"><strong>Reading these figures.</strong> '
            + " ".join(html.escape(n) for n in notes) + "</p>")


def render_html(f: dict) -> str:
    s = f["summary"]
    recs = "".join(f"<li>{html.escape(r)}</li>" for r in build_recommendations(f))

    reorder_rows = (
        _table_html(
            f["reorder_now"],
            [("product_name", "Product", "text"), ("product_id", "ID", "text"),
             ("warehouse", "Warehouse", "text"), ("stock_quantity", "Stock", "number"),
             ("reorder_level", "Reorder level", "number"),
             ("stock_value", "Stock value", "money")],
        )
        if len(f["reorder_now"]) > 0
        else '<p class="empty">No product is currently at or below its reorder level.</p>'
    )

    style = f"""
:root {{
  --ink: {t.INK}; --ink-soft: {t.INK_SOFT}; --text: {t.TEXT}; --muted: {t.MUTED};
  --border: {t.BORDER}; --surface: {t.SURFACE}; --canvas: {t.CANVAS};
  --surface-alt: {t.SURFACE_ALT}; --positive: {t.POSITIVE}; --caution: {t.CAUTION};
  --negative: {t.NEGATIVE}; --teal: {t.TEAL};
}}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:var(--canvas); color:var(--text);
       font-family:{t.FONT_STACK}; font-size:14px; line-height:1.55; }}
.sheet {{ max-width:1080px; margin:0 auto; background:var(--surface);
          box-shadow:0 1px 3px rgba(16,36,62,.08); }}
header.masthead {{ background:var(--ink); color:#fff; padding:28px 40px 24px; }}
.masthead h1 {{ margin:0; font-size:24px; font-weight:600; letter-spacing:-.01em; }}
.masthead .sub {{ margin-top:4px; font-size:14px; color:#B9C6D6; }}
.masthead .meta {{ margin-top:14px; font-size:12px; color:#8FA3BA;
                   border-top:1px solid rgba(255,255,255,.14); padding-top:12px; }}
main {{ padding:0 40px 40px; }}
section {{ padding-top:28px; }}
h2 {{ font-size:12px; font-weight:600; letter-spacing:.09em; text-transform:uppercase;
      color:var(--muted); margin:0 0 14px; padding-bottom:8px;
      border-bottom:1px solid var(--border); }}
h3 {{ font-size:14px; font-weight:600; color:var(--ink-soft); margin:22px 0 8px; }}
p {{ margin:0 0 10px; }}
ul {{ margin:0 0 10px; padding-left:20px; }}
li {{ margin-bottom:6px; }}
.cards {{ display:grid; grid-template-columns:repeat(4,1fr); gap:1px;
          background:var(--border); border:1px solid var(--border); }}
.card {{ background:var(--surface); padding:14px 16px 12px; }}
.card-label {{ font-size:10.5px; font-weight:600; letter-spacing:.07em;
               text-transform:uppercase; color:var(--muted); }}
.card-value {{ font-size:26px; font-weight:600; letter-spacing:-.02em;
               margin:6px 0 4px; font-variant-numeric:tabular-nums; }}
.card-note {{ font-size:11px; color:var(--muted); line-height:1.35; }}
.table-wrap {{ overflow-x:auto; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th, td {{ padding:8px 10px; text-align:left; border-bottom:1px solid var(--border); }}
th {{ font-size:10.5px; font-weight:600; letter-spacing:.06em; text-transform:uppercase;
      color:var(--muted); border-bottom:1px solid var(--ink); white-space:nowrap; }}
td.num, th.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
tbody tr:nth-child(even) {{ background:var(--surface-alt); }}
.finding {{ border-left:3px solid var(--teal); padding:2px 0 2px 14px; margin:0 0 12px; }}
.finding strong {{ color:var(--ink-soft); }}
.callout {{ background:var(--surface-alt); border:1px solid var(--border);
            border-left:3px solid var(--caution); padding:12px 16px; font-size:13px; }}
.callout.method {{ border-left-color:var(--muted); }}
ol.recs {{ margin:0; padding-left:20px; }}
ol.recs li {{ margin-bottom:10px; }}
.empty {{ color:var(--muted); font-style:italic; }}
footer {{ padding:20px 40px 32px; font-size:11.5px; color:var(--muted);
          border-top:1px solid var(--border); }}
@media print {{
  body {{ background:#fff; }}
  .sheet {{ box-shadow:none; max-width:none; }}
  section {{ break-inside:avoid; }}
}}
@media (max-width:820px) {{
  .cards {{ grid-template-columns:repeat(2,1fr); }}
  main, header.masthead, footer {{ padding-left:20px; padding-right:20px; }}
}}
"""


    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(REPORT_TITLE)}</title>
<style>{style}</style>
</head>
<body>
<div class="sheet">
<header class="masthead">
  <h1>{html.escape(REPORT_TITLE)}</h1>
  <div class="sub">{html.escape(REPORT_SUBTITLE)}</div>
  <div class="meta">Reporting period {html.escape(f['period_start'])} &ndash;
    {html.escape(f['period_end'])} ({f['months_observed']} months)
    &nbsp;·&nbsp; Generated {date.today().isoformat()}
    &nbsp;·&nbsp; Source: enterprise sales data warehouse</div>
</header>
<main>

<section>
  <h2>Performance at a glance</h2>
  {_kpi_cards_html(f)}
</section>

<section>
  <h2>Where the business is growing</h2>
  <p class="finding"><strong>{html.escape(f['best_region']['region_name'])}</strong> is the
    strongest region: {t.money(f['best_region']['total_revenue'])} of revenue
    ({t.percent(f['best_region']['revenue_share_pct'])} of the total) at
    {t.percent(f['best_region']['profit_margin_pct'])} margin across
    {int(f['best_region']['countries'])} countries.</p>
  <p class="finding">Regional margins span only
    {t.percent(f['worst_margin_region']['profit_margin_pct'])} to
    {t.percent(f['best_margin_region']['profit_margin_pct'])}, so the profit gap between regions is
    driven by revenue mix rather than regional pricing or cost.</p>
  {_table_html(f['regions'], [
      ("region_name", "Region", "text"),
      ("countries", "Countries", "number"),
      ("total_revenue", "Revenue", "money"),
      ("total_profit", "Profit", "money"),
      ("profit_margin_pct", "Margin", "percent"),
      ("total_orders", "Orders", "number"),
      ("avg_order_value", "AOV", "money"),
      ("revenue_share_pct", "Share", "percent"),
  ])}
  <h3>Category mix</h3>
  {_table_html(f['categories'], [
      ("category", "Category", "text"),
      ("total_revenue", "Revenue", "money"),
      ("total_profit", "Profit", "money"),
      ("profit_margin_pct", "Margin", "percent"),
      ("units_sold", "Units", "number"),
      ("revenue_share_pct", "Share", "percent"),
  ])}
</section>

<section>
  <h2>Profitability</h2>
  <p class="finding"><strong>{html.escape(f['best_product_revenue']['product_name'])}</strong>
    leads on revenue ({t.money(f['best_product_revenue']['total_revenue'])},
    {t.percent(f['best_product_revenue']['profit_margin_pct'])} margin);
    <strong>{html.escape(f['best_product_profit']['product_name'])}</strong> contributes the most
    profit ({t.money(f['best_product_profit']['total_profit'])}).</p>
  <p class="finding"><strong>{html.escape(f['worst_margin_product']['product_name'])}</strong> is
    the margin outlier at {t.percent(f['worst_margin_product']['margin_pct'])} on
    {t.money(f['worst_margin_product']['total_revenue'])} of revenue &mdash; status
    {t.margin_status(f['worst_margin_product']['margin_pct'])}.</p>
  <h3>Lowest-margin products</h3>
  {_table_html(f['low_margin'], [
      ("product_name", "Product", "text"),
      ("category", "Category", "text"),
      ("total_revenue", "Revenue", "money"),
      ("total_profit", "Profit", "money"),
      ("margin_pct", "Margin", "percent"),
  ])}
</section>

<section>
  <h2>Customers</h2>
  <p class="finding">{t.number(s['Total Customers'][0])} customers transacted in the period, of
    {t.number(f['customers_on_file'])} on file, averaging
    {s['Total Orders'][0] / s['Total Customers'][0]:,.1f} orders each.
    {t.percent(s['Repeat Customer Rate %'][0])} ordered more than once and the top 10 accounts hold
    {t.percent(f['top10_revenue_share'])} of revenue.</p>
  {_customer_caveat_html(f)}
  {_table_html(f['segments'], [
      ("segment", "Segment", "text"),
      ("total_customers", "Customers", "number"),
      ("total_revenue", "Revenue", "money"),
      ("profit_margin_pct", "Margin", "percent"),
      ("avg_order_value", "AOV", "money"),
      ("revenue_per_customer", "Revenue / customer", "money"),
      ("repeat_customer_rate_pct", "Repeat rate", "percent"),
  ])}
  <h3>Top 10 customers by revenue</h3>
  {_table_html(f['top_customers'], [
      ("customer_name", "Customer", "text"),
      ("segment", "Segment", "text"),
      ("region_name", "Region", "text"),
      ("total_revenue", "Revenue", "money"),
      ("total_orders", "Orders", "number"),
      ("avg_order_value", "AOV", "money"),
  ])}
</section>

<section>
  <h2>Inventory risk</h2>
  <p class="finding">{t.money(f['stock_value'])} of stock at cost across
    {len(f['inventory'])} product/warehouse positions, turning over
    {t.ratio(s['Inventory Turnover Ratio'][0])} across the period.
    {len(f['reorder_now'])} position(s) sit at or below the reorder trigger and
    {len(f['at_risk'])} more are within 25% of it.</p>
  <p class="callout method"><strong>Reading turnover.</strong> The ratio divides units sold across
    the full {f['months_observed']}-month period by a point-in-time stock snapshot, so it ranks
    relative velocity between products rather than reporting an annualised turn rate.</p>
  {reorder_rows}
</section>

<section>
  <h2>Outlook</h2>
  <p class="finding">A seasonal linear-trend model projects
    <strong>{t.money(f['forecast_total'])}</strong> of revenue for {f['forecast_label']}, within a
    modelled range of {t.money(f['forecast_lower_total'])} to
    {t.money(f['forecast_upper_total'])} &mdash;
    {t.signed_percent(f['forecast_vs_baseline_pct'])} against the same months a year earlier
    ({f['baseline_label']}: {t.money(f['baseline_total'])}). The comparison is year-on-year because
    the trailing six months end on the November/December peak, where a normal seasonal step-down
    would read as decline.</p>
  {_table_html(f['forecast_months'], [
      ("month", "Month", "text"),
      ("forecast_lower", "Low", "money_compact"),
      ("forecast_revenue", "Projected", "money"),
      ("forecast_upper", "High", "money_compact"),
      ("linear_trend", "Trend", "money_compact"),
  ])}
  <p class="callout method"><strong>Method.</strong> Ordinary least squares on the monthly revenue
    series gives the underlying trend; that trend is scaled by a month-of-year seasonal index
    derived from the same history. The range is &plusmn;1.96 residual standard deviations of the
    in-sample fit. The projection assumes pricing, product mix, and market conditions hold. It is
    a planning input, not a commitment or a guaranteed outcome.</p>
</section>

<section>
  <h2>Recommendations</h2>
  <ol class="recs">{recs}</ol>
</section>

<section>
  <h2>Data quality</h2>
  <p class="callout"><strong>{t.money(f['unassigned_revenue'])}</strong>
    ({t.percent(f['unassigned_share'])} of revenue, {t.number(f['unassigned_orders'])} orders)
    belongs to customers whose source region could not be resolved. The ETL preserves that revenue
    in an &ldquo;{html.escape(UNKNOWN_REGION)}&rdquo; bucket rather than dropping it, and the
    regional rankings on this page exclude the bucket so a data-quality artefact is not reported as
    a market finding. A further {t.number(f['unclassified_customers'])} customers
    ({t.percent(f['unclassified_share'])} of revenue) arrived with a blank segment and are held in
    an &ldquo;{html.escape(UNCLASSIFIED_SEGMENT)}&rdquo; bucket, excluded from segment rankings on
    the same basis.</p>
</section>

</main>
<footer>
  Figures are computed from the KPI tables in <code>reports/</code> by
  <code>python/build_kpis.py</code>. Metric definitions, and their matching T-SQL and DAX
  implementations, are in <code>docs/KPI_DEFINITIONS.md</code>.
</footer>
</div>
</body>
</html>
"""


def main() -> None:
    kpi = load_kpis()
    findings = build_findings(kpi)
    findings["summary_frame"] = kpi["executive_summary"]

    md_path = REPORTS_DIR / "executive_insights.md"
    md_path.write_text(render_markdown(findings), encoding="utf-8")
    logger.info("Executive insights (Markdown) written to %s", md_path)

    html_path = REPORTS_DIR / "executive_insights.html"
    html_path.write_text(render_html(findings), encoding="utf-8")
    logger.info("Executive insights (HTML) written to %s", html_path)


if __name__ == "__main__":
    main()
