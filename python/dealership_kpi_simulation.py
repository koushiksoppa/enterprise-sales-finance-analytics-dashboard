"""
dealership_kpi_simulation.py
----------------------------
Dealership operating KPIs - sales funnel conversion and inventory ageing -
computed on SIMULATED showroom data.

Why simulated: real showroom-level enquiry, booking and stock data is
private to each dealer and is not published. This script shows how a dealer
group would measure the operating levers that the market brief
(AUTO_RETAIL_BRIEF.md) points to. The method is the deliverable; the numbers
are illustrative and are labelled as such in every output.

What is real and what is assumed:
  * REAL: month-to-month demand pattern per brand. Each simulated showroom's
    enquiry volume follows its brand's actual FADA monthly retail trend
    (data/external/fada_oem_retail_2026.csv), so seasonality is genuine.
  * ASSUMED: showroom base volume, funnel conversion rates, average vehicle
    value, stock policy and holding-cost rate. All are in ASSUMPTIONS below and
    are written to the outputs so a reader can see and challenge them.

Outputs (reports/auto_retail/, all prefixed sim_):
    sim_funnel_monthly.csv       enquiries -> test drives -> bookings -> deliveries
    sim_funnel_summary.csv       conversion rates by showroom
    sim_inventory_ageing.csv     stock on hand at 30 Sep by age bucket, holding cost
    DEALERSHIP_KPI_FRAMEWORK.md  KPI definitions, owners, cadence, simulated results
    screenshots/sim_funnel_conversion.png

Run:
    python dealership_kpi_simulation.py
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logging.getLogger("matplotlib").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
EXT_DIR = BASE_DIR / "data" / "external"
OUT_DIR = BASE_DIR / "reports" / "auto_retail"
IMG_DIR = BASE_DIR / "screenshots"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SEED = 42
SNAPSHOT = pd.Timestamp("2026-09-30")
HOLDING_COST_PER_DAY = 0.0004   # 0.04% of vehicle value per day (~14.6% a year inventory-funding cost)
AGE_BUCKETS = [0, 30, 60, 90, 10_000]
AGE_LABELS = ["0-30 days", "31-60 days", "61-90 days", "90+ days"]

# One simulated showroom per franchise brand. Every value here is an
# assumption for illustration, not a measured figure.
ASSUMPTIONS = pd.DataFrame([
    # showroom, FADA entity used for the demand pattern, Feb enquiries,
    # enquiry->test drive, test drive->booking, booking->delivery,
    # average vehicle value (INR), stock ordered vs deliveries,
    # slow-variant share of stock ordered, slow-variant share of customer demand
    ("Toyota showroom", "TOYOTA KIRLOSKAR MOTOR PVT LTD", 900, 0.45, 0.32, 0.90, 1_400_000, 1.10, 0.18, 0.12),
    ("Honda Cars showroom", "HONDA CARS INDIA LTD", 420, 0.42, 0.28, 0.88, 1_100_000, 1.10, 0.22, 0.12),
    ("MG Motor showroom", "JSW MG MOTOR INDIA PVT LTD", 480, 0.40, 0.25, 0.87, 1_600_000, 1.10, 0.25, 0.12),
    ("Mercedes-Benz showroom", "MERCEDES-BENZ GROUP", 110, 0.55, 0.30, 0.92, 7_500_000, 1.10, 0.20, 0.15),
    ("Ather showroom", "ATHER ENERGY LTD", 1_300, 0.50, 0.38, 0.93, 150_000, 1.05, 0.12, 0.12),
], columns=["showroom", "fada_oem", "feb_enquiries", "enq_to_td", "td_to_booking",
            "booking_to_delivery", "avg_vehicle_value_inr", "stock_order_factor",
            "slow_share_of_orders", "slow_share_of_demand"])

BLUE, GRAY = "#2a78d6", "#b9b8b3"
INK, INK_SOFT, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e6e5e0", "#fcfcfb"


def demand_index() -> pd.DataFrame:
    """Each brand's real monthly retail volume, indexed to February = 1.0."""
    oem = pd.read_csv(EXT_DIR / "fada_oem_retail_2026.csv")
    oem = oem[oem.oem.isin(ASSUMPTIONS.fada_oem)]
    oem = oem.sort_values("month")
    oem["index"] = oem.groupby("oem").units_2026.transform(lambda s: s / s.iloc[0])
    return oem[["month", "oem", "index"]]


def simulate_funnel(rng: np.random.Generator) -> pd.DataFrame:
    idx = demand_index()
    rows = []
    for a in ASSUMPTIONS.itertuples():
        for m in idx[idx.oem == a.fada_oem].itertuples():
            enq = rng.poisson(a.feb_enquiries * m.index)
            td = rng.binomial(enq, a.enq_to_td)
            book = rng.binomial(td, a.td_to_booking)
            deliv = rng.binomial(book, a.booking_to_delivery)
            rows.append((a.showroom, m.month, enq, td, book, deliv))
    return pd.DataFrame(rows, columns=["showroom", "month", "enquiries", "test_drives", "bookings", "deliveries"])


def funnel_summary(f: pd.DataFrame) -> pd.DataFrame:
    s = f.groupby("showroom")[["enquiries", "test_drives", "bookings", "deliveries"]].sum()
    s["enquiry_to_test_drive_pct"] = s.test_drives / s.enquiries * 100
    s["test_drive_to_booking_pct"] = s.bookings / s.test_drives * 100
    s["booking_to_delivery_pct"] = s.deliveries / s.bookings * 100
    s["enquiry_to_delivery_pct"] = s.deliveries / s.enquiries * 100
    return s.reset_index().sort_values("enquiry_to_delivery_pct", ascending=False)


def simulate_inventory(f: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Stock by variant group. Ageing comes from model-mix mismatch: when slow-selling
    variants are a larger share of what is ordered than of what customers buy, those
    units accumulate and age. Within each variant group, the oldest unit sells first."""
    rows = []
    for a in ASSUMPTIONS.itertuples():
        fs = f[f.showroom == a.showroom].sort_values("month")
        stock: dict[str, list[pd.Timestamp]] = {"fast": [], "slow": []}
        for m in fs.itertuples():
            start = pd.Timestamp(m.month + "-01")
            n_in = int(round(m.deliveries * a.stock_order_factor))
            n_slow_in = rng.binomial(n_in, a.slow_share_of_orders)
            for group, n in (("slow", n_slow_in), ("fast", n_in - n_slow_in)):
                days = rng.integers(0, start.days_in_month, n)
                stock[group].extend(start + pd.to_timedelta(days, unit="D"))
                stock[group].sort()
            want_slow = rng.binomial(m.deliveries, a.slow_share_of_demand)
            sold_slow = min(want_slow, len(stock["slow"]))
            sold_fast = min(m.deliveries - sold_slow, len(stock["fast"]))
            stock["slow"] = stock["slow"][sold_slow:]
            stock["fast"] = stock["fast"][sold_fast:]
        on_hand = pd.Series(stock["fast"] + stock["slow"], dtype="datetime64[ns]")
        age = (SNAPSHOT - on_hand).dt.days.clip(lower=0)
        bucket = pd.cut(age, AGE_BUCKETS, labels=AGE_LABELS, right=True, include_lowest=True)
        for label in AGE_LABELS:
            mask = bucket == label
            units = int(mask.sum())
            holding = float((age[mask] * a.avg_vehicle_value_inr * HOLDING_COST_PER_DAY).sum())
            rows.append((a.showroom, label, units, units * a.avg_vehicle_value_inr, round(holding)))
    return pd.DataFrame(rows, columns=["showroom", "age_bucket", "units", "stock_value_inr",
                                       "holding_cost_to_date_inr"])


def chart_funnel(summary: pd.DataFrame) -> Path:
    s = summary.sort_values("enquiry_to_delivery_pct")
    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.22, right=0.95, top=0.78, bottom=0.15)
    ax.barh(s.showroom, s.enquiry_to_delivery_pct, color=BLUE, height=0.55)
    for i, v in enumerate(s.enquiry_to_delivery_pct):
        ax.text(v + 0.3, i, f"{v:.1f}%", va="center", fontsize=9, color=INK)
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="x", colors=MUTED, labelsize=9, length=0)
    ax.tick_params(axis="y", colors=INK, labelsize=10, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel("Enquiry-to-delivery conversion, Feb-Sep 2026 (%)", color=MUTED, fontsize=9)
    fig.text(0.02, 0.965, "Enquiry-to-delivery conversion by showroom (SIMULATED DATA)",
             fontsize=13, fontweight="bold", color=INK, va="top")
    fig.text(0.02, 0.895, "Illustrates the KPI, not real dealer performance. Demand pattern follows each "
             "brand's real FADA monthly trend; conversion rates are assumptions.", fontsize=9, color=INK_SOFT, va="top")
    path = IMG_DIR / "sim_funnel_conversion.png"
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path


def write_framework(summary: pd.DataFrame, inv: pd.DataFrame) -> Path:
    aged = inv[inv.age_bucket.isin(["61-90 days", "90+ days"])].groupby("showroom").units.sum()
    total = inv.groupby("showroom").units.sum()
    aged_pct = (aged / total * 100).fillna(0)
    worst = aged_pct.idxmax()
    holding = inv.groupby("showroom").holding_cost_to_date_inr.sum()
    aged_holding = inv[inv.age_bucket.isin(["61-90 days", "90+ days"])].holding_cost_to_date_inr.sum()
    sim_table = "\n".join(
        f"| {r.showroom} | {r.enquiries:,} | {r.enquiry_to_test_drive_pct:.1f}% | {r.test_drive_to_booking_pct:.1f}% "
        f"| {r.booking_to_delivery_pct:.1f}% | {r.enquiry_to_delivery_pct:.1f}% | {total[r.showroom]:,} "
        f"| {aged_pct[r.showroom]:.0f}% |"
        for r in summary.itertuples())
    assumptions_table = "\n".join(
        f"| {a.showroom} | {a.feb_enquiries:,} | {a.enq_to_td:.0%} | {a.td_to_booking:.0%} | {a.booking_to_delivery:.0%} "
        f"| ₹{a.avg_vehicle_value_inr:,} | {a.stock_order_factor:.2f}x | {a.slow_share_of_orders:.0%} | {a.slow_share_of_demand:.0%} |"
        for a in ASSUMPTIONS.itertuples())
    text = f"""# Dealership KPI Framework

How a dealer group turns the market brief into weekly showroom management. The **framework** (what to measure,
who owns it, how often it is reviewed, what triggers action) is the deliverable. The results table uses
**simulated data** because real showroom data is private; it shows the KPIs working, not real performance.

## KPIs

| KPI | Formula | Owner | Review | Action trigger |
|---|---|---|---|---|
| Enquiry → test drive % | test drives ÷ enquiries | Sales manager | Weekly | Below brand target for 2 weeks: review lead follow-up time and test-drive fleet availability |
| Test drive → booking % | bookings ÷ test drives | Sales manager | Weekly | Falls 5 pts below trailing average: review pricing, finance and exchange offers |
| Booking → delivery % | deliveries ÷ bookings | Showroom GM | Weekly | Below 85%: audit cancellations by reason (finance rejection, stock wait, competitor) |
| Enquiry → delivery % | deliveries ÷ enquiries | Showroom GM | Monthly | Compare across showrooms of the same brand; investigate the bottom performer |
| Days in stock | snapshot date − arrival date, per vehicle | Inventory manager | Weekly | Any unit over 60 days: prioritise in sales targets or reallocate between outlets |
| Aged stock % | units over 60 days ÷ units in stock | Business head | Monthly | Above 20%: reduce next order for that model |
| Inventory holding cost | Σ days in stock × vehicle value × daily funding rate | Finance | Monthly | Track against margin per vehicle; ageing erodes margin daily |
| First-service retention % | customers returning for 1st service ÷ deliveries due | Service manager | Monthly | Below 80%: call-back campaign; service is the long-term profit pool |

## Simulated results, February–September 2026

| Showroom | Enquiries | Enq → TD | TD → booking | Booking → delivery | Enq → delivery | Stock on 30 Sep | Stock over 60 days |
|---|---:|---:|---:|---:|---:|---:|---:|
{sim_table}

Reading the simulation: the showroom with the highest share of stock over 60 days is the **{worst}**
({aged_pct[worst]:.0f}%). Stock over 60 days has already accumulated ₹{aged_holding / 1e5:,.1f} lakh of holding
cost across showrooms. The cause in this model is variant mix: slow-selling variants are a bigger share of what is
ordered than of what customers buy. The action is to cut slow variants from the next order and push aged units
with targeted offers, not to cut the brand's total order. First-service retention is defined above but not simulated.

![Funnel conversion](../../screenshots/sim_funnel_conversion.png)

## Assumptions (illustrative, not measured)

| Showroom | Feb enquiries | Enq → TD | TD → booking | Booking → delivery | Avg vehicle value | Stock ordered vs deliveries | Slow variants in orders | Slow variants in demand |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
{assumptions_table}

- Monthly enquiry volume follows each brand's **real** FADA retail trend, indexed to February.
- Holding cost uses {HOLDING_COST_PER_DAY:.2%} of vehicle value per day (about {HOLDING_COST_PER_DAY * 365:.1%} a year).
- Aged stock comes from variant-mix mismatch: slow variants' share of orders exceeds their share of demand.
  Within each variant group, the oldest unit is delivered first. Random seed {SEED}, so every run gives the same numbers.
- Generated by `python/dealership_kpi_simulation.py`.
"""
    path = OUT_DIR / "DEALERSHIP_KPI_FRAMEWORK.md"
    path.write_text(text, encoding="utf-8")
    return path


def main() -> None:
    rng = np.random.default_rng(SEED)
    funnel = simulate_funnel(rng)
    summary = funnel_summary(funnel)
    inv = simulate_inventory(funnel, rng)
    funnel.to_csv(OUT_DIR / "sim_funnel_monthly.csv", index=False)
    summary.round(2).to_csv(OUT_DIR / "sim_funnel_summary.csv", index=False)
    inv.to_csv(OUT_DIR / "sim_inventory_ageing.csv", index=False)
    logger.info("Chart written: %s", chart_funnel(summary).relative_to(BASE_DIR))
    logger.info("Framework written: %s", write_framework(summary, inv).relative_to(BASE_DIR))


if __name__ == "__main__":
    main()
