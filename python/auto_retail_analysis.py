"""
auto_retail_analysis.py
-----------------------
Auto-retail market analysis on REAL registration data published by FADA
(Federation of Automobile Dealers Associations, India), collected with the
Ministry of Road Transport & Highways from ~1,468 of 1,469 RTOs.

Question this answers, from the seat of a multi-brand dealer group:

    Our franchise brands are Toyota, Honda Cars, JSW MG Motor and
    Mercedes-Benz (passenger vehicles) and Ather Energy (two-wheelers).
    Are they winning or losing ground in the national market, and what
    should the dealer group do about it?

Inputs  (data/external/, transcribed from FADA's monthly press releases,
         Feb-Sep 2026 each with the same month of 2025 - see SOURCES.md):
    fada_oem_retail_2026.csv      OEM-wise monthly retail units, PV and 2W
    fada_segment_totals_2026.csv  segment totals per month
    fada_ev_share_2026.csv        EV share of retail per segment per month

Outputs (reports/auto_retail/ and screenshots/):
    brand_performance.csv         period units, YoY growth, share, share change
    brand_monthly.csv             monthly units, share and YoY per OEM
    segment_monthly.csv           monthly segment totals and YoY
    portfolio_summary.csv         the dealer-group brand portfolio rolled up
    AUTO_RETAIL_BRIEF.md          decision memo, every figure computed here
    screenshots/auto_*.png        charts used by the README and the brief

Every input row is validated: OEM rows must sum exactly to FADA's published
segment total for every month, or the script stops.

Run:
    python auto_retail_analysis.py
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)
logging.getLogger("matplotlib").setLevel(logging.WARNING)

BASE_DIR = Path(__file__).resolve().parent.parent
EXT_DIR = BASE_DIR / "data" / "external"
OUT_DIR = BASE_DIR / "reports" / "auto_retail"
IMG_DIR = BASE_DIR / "screenshots"
OUT_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR.mkdir(parents=True, exist_ok=True)

SEGMENT_NAMES = {"PV": "Passenger vehicles", "2W": "Two-wheelers"}

# The dealer group's franchise brands, mapped from FADA's legal-entity names.
PORTFOLIO = {
    "TOYOTA KIRLOSKAR MOTOR PVT LTD": "Toyota",
    "HONDA CARS INDIA LTD": "Honda Cars",
    "JSW MG MOTOR INDIA PVT LTD": "MG Motor",
    "MERCEDES-BENZ GROUP": "Mercedes-Benz",
    "ATHER ENERGY LTD": "Ather",
}

# Short display names for the other OEMs shown on charts.
SHORT = {
    "MARUTI SUZUKI INDIA LTD": "Maruti Suzuki",
    "TATA MOTORS LTD": "Tata Motors",
    "MAHINDRA & MAHINDRA LIMITED": "Mahindra",
    "HYUNDAI MOTOR INDIA LTD": "Hyundai",
    "KIA INDIA PRIVATE LIMITED": "Kia",
    "SKODA AUTO VOLKSWAGEN GROUP": "Skoda-VW",
    "RENAULT INDIA PVT LTD": "Renault",
    "NISSAN MOTOR INDIA PVT LTD": "Nissan",
    "BMW INDIA PVT LTD": "BMW",
    "VINFAST AUTO INDIA PVT LTD": "VinFast",
    "FORCE MOTORS LIMITED": "Force Motors",
    "STELLANTIS GROUP": "Stellantis",
    "BYD INDIA PRIVATE LIMITED": "BYD",
    "JAGUAR LAND ROVER INDIA LIMITED": "JLR",
    **PORTFOLIO,
}

# Chart palette: the validated reference palette from the dataviz guidance
# (categorical blue/orange pass colour-blind separation on a light surface).
BLUE, ORANGE, GRAY = "#2a78d6", "#eb6834", "#b9b8b3"
INK, INK_SOFT, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e6e5e0", "#fcfcfb"


# ------------------------------------------------------------------ load --
def load() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    oem = pd.read_csv(EXT_DIR / "fada_oem_retail_2026.csv")
    tot = pd.read_csv(EXT_DIR / "fada_segment_totals_2026.csv")
    ev = pd.read_csv(EXT_DIR / "fada_ev_share_2026.csv")

    # Bajaj is reported as "BAJAJ AUTO GROUP" in some months and
    # "BAJAJ AUTO LTD" in others; Greaves gains/loses "PVT". Normalise so the
    # same company is one entity across months.
    oem["oem"] = oem["oem"].replace({
        "BAJAJ AUTO GROUP": "BAJAJ AUTO LTD",
        "GREAVES ELECTRIC MOBILITY PVT LTD": "GREAVES ELECTRIC MOBILITY LTD",
    })
    return oem, tot, ev


def validate(oem: pd.DataFrame, tot: pd.DataFrame) -> None:
    """OEM rows must reproduce FADA's published totals exactly."""
    dupes = oem.duplicated(["month", "segment", "oem"]).sum()
    if dupes:
        raise ValueError(f"{dupes} duplicate month/segment/OEM rows")
    summed = oem.groupby(["month", "segment"])[["units_2026", "units_2025"]].sum()
    check = summed.join(tot.set_index(["month", "segment"]), rsuffix="_published")
    gaps = check[(check.units_2026 != check.units_2026_published)
                 | (check.units_2025 != check.units_2025_published)]
    if not gaps.empty:
        raise ValueError(f"OEM rows do not sum to published totals:\n{gaps}")
    logger.info("Validated %d OEM rows: every month/segment sums to FADA's total", len(oem))


# --------------------------------------------------------------- analyse --
def brand_performance(oem: pd.DataFrame, tot: pd.DataFrame) -> pd.DataFrame:
    seg_tot = tot.groupby("segment")[["units_2026", "units_2025"]].sum()
    g = oem.groupby(["segment", "oem"])[["units_2026", "units_2025"]].sum().reset_index()
    g["yoy_growth_pct"] = (g.units_2026 / g.units_2025.where(g.units_2025 > 0) - 1) * 100
    g["share_2026_pct"] = g.units_2026 / g.segment.map(seg_tot.units_2026) * 100
    g["share_2025_pct"] = g.units_2025 / g.segment.map(seg_tot.units_2025) * 100
    g["share_change_bps"] = (g.share_2026_pct - g.share_2025_pct) * 100
    seg_growth = (seg_tot.units_2026 / seg_tot.units_2025 - 1) * 100
    g["segment_growth_pct"] = g.segment.map(seg_growth)
    g["growth_vs_market_pts"] = g.yoy_growth_pct - g.segment_growth_pct
    g["brand"] = g.oem.map(SHORT).fillna(g.oem.str.title())
    g["is_portfolio_brand"] = g.oem.isin(PORTFOLIO)
    return g.sort_values(["segment", "units_2026"], ascending=[True, False])


def brand_monthly(oem: pd.DataFrame, tot: pd.DataFrame) -> pd.DataFrame:
    m = oem.merge(tot, on=["month", "segment"], suffixes=("", "_segment"))
    m["share_2026_pct"] = m.units_2026 / m.units_2026_segment * 100
    m["share_2025_pct"] = m.units_2025 / m.units_2025_segment * 100
    m["yoy_growth_pct"] = (m.units_2026 / m.units_2025.where(m.units_2025 > 0) - 1) * 100
    m["brand"] = m.oem.map(SHORT).fillna(m.oem.str.title())
    return m.drop(columns=["units_2026_segment", "units_2025_segment"]).sort_values(["month", "segment"])


def segment_monthly(tot: pd.DataFrame, ev: pd.DataFrame) -> pd.DataFrame:
    s = tot.merge(ev, on=["month", "segment"])
    s["yoy_growth_pct"] = (s.units_2026 / s.units_2025 - 1) * 100
    s["ev_units_2026_est"] = (s.units_2026 * s.ev_share_2026_pct / 100).round().astype(int)
    return s.sort_values(["segment", "month"])


def portfolio_summary(perf: pd.DataFrame) -> pd.DataFrame:
    p = perf[perf.is_portfolio_brand]
    rows = []
    for seg, grp in p.groupby("segment"):
        seg_all = perf[perf.segment == seg]
        u26, u25 = grp.units_2026.sum(), grp.units_2025.sum()
        t26, t25 = seg_all.units_2026.sum(), seg_all.units_2025.sum()
        rows.append({
            "segment": seg,
            "brands": ", ".join(grp.brand),
            "units_2026": u26, "units_2025": u25,
            "yoy_growth_pct": (u26 / u25 - 1) * 100,
            "segment_growth_pct": (t26 / t25 - 1) * 100,
            "share_2026_pct": u26 / t26 * 100, "share_2025_pct": u25 / t25 * 100,
            "share_change_bps": (u26 / t26 - u25 / t25) * 1e4,
            "units_if_held_share": round(u25 / t25 * t26),
        })
    out = pd.DataFrame(rows)
    out["units_gap_vs_held_share"] = out.units_2026 - out.units_if_held_share
    return out


# ---------------------------------------------------------------- charts --
def _style(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=9, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def _title(fig, title: str, subtitle: str) -> None:
    fig.text(0.02, 0.965, title, fontsize=13, fontweight="bold", color=INK, va="top")
    fig.text(0.02, 0.905, subtitle, fontsize=9.5, color=INK_SOFT, va="top")
    fig.text(0.02, 0.02, "Source: FADA monthly vehicle retail data, Feb-Sep 2026 vs Feb-Sep 2025. Analysis: this repository.",
             fontsize=7.5, color=MUTED)


def chart_growth_vs_market(perf: pd.DataFrame) -> Path:
    """Portfolio brands' YoY growth against their own segment's growth."""
    p = perf[perf.is_portfolio_brand].sort_values("yoy_growth_pct")
    fig, ax = plt.subplots(figsize=(10, 4.6), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.22, right=0.95, top=0.80, bottom=0.14)
    y = range(len(p))
    colors = [ORANGE if s == "2W" else BLUE for s in p.segment]
    ax.barh(list(y), p.yoy_growth_pct, color=colors, height=0.55)
    for i, (_, r) in enumerate(p.iterrows()):
        ax.plot([r.segment_growth_pct] * 2, [i - 0.38, i + 0.38], color=INK, linewidth=1.6)
        label = f"{r.yoy_growth_pct:+.2f}%" if abs(r.yoy_growth_pct) < 0.1 else f"{r.yoy_growth_pct:+.1f}%"
        ax.text(max(r.yoy_growth_pct, 0) + 1.2, i, label, va="center", fontsize=9, color=INK)
    ax.set_yticks(list(y), [f"{b}  ({'two-wheelers' if s == '2W' else 'cars'})" for b, s in zip(p.brand, p.segment)])
    ax.set_xlabel("Retail growth, Feb-Sep 2026 vs Feb-Sep 2025 (%)", color=MUTED, fontsize=9)
    _style(ax)
    ax.tick_params(axis="y", colors=INK, labelsize=10)
    ax.set_xlim(0, max(p.yoy_growth_pct.max(), 25) * 1.15)
    seg = perf.groupby("segment").segment_growth_pct.first()
    ather = p[p.brand == "Ather"].iloc[0]
    multiple = ather.yoy_growth_pct / ather.segment_growth_pct
    _title(fig, f"Every portfolio car brand grew slower than the car market; Ather grew {multiple:.1f}x its market's pace",
           f"Bars: brand growth. Black tick: its segment's growth (cars {seg['PV']:+.1f}%, two-wheelers {seg['2W']:+.1f}%).")
    path = IMG_DIR / "auto_growth_vs_market.png"
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path


def chart_share_change(perf: pd.DataFrame) -> Path:
    """Who took passenger-vehicle share: change in share, bps, OEMs >= 0.3% share."""
    pv = perf[(perf.segment == "PV") & (perf.oem != "Others") & (perf.share_2026_pct >= 0.3)]
    pv = pv.sort_values("share_change_bps")
    fig, ax = plt.subplots(figsize=(10, 5.6), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.17, right=0.95, top=0.84, bottom=0.11)
    colors = [BLUE if p else GRAY for p in pv.is_portfolio_brand]
    ax.barh(pv.brand, pv.share_change_bps, color=colors, height=0.6)
    ax.axvline(0, color=INK_SOFT, linewidth=0.8)
    for i, (_, r) in enumerate(pv.iterrows()):
        off = 4 if r.share_change_bps >= 0 else -4
        ax.text(r.share_change_bps + off, i, f"{r.share_change_bps:+.0f}", va="center",
                ha="left" if off > 0 else "right", fontsize=8.5,
                color=INK if r.is_portfolio_brand else INK_SOFT,
                fontweight="bold" if r.is_portfolio_brand else "normal")
    ax.set_xlabel("Change in passenger-vehicle market share (basis points)", color=MUTED, fontsize=9)
    _style(ax)
    ax.tick_params(axis="y", colors=INK_SOFT, labelsize=9.5)
    for lbl in ax.get_yticklabels():
        if lbl.get_text() in PORTFOLIO.values():
            lbl.set_fontweight("bold")
            lbl.set_color(INK)
    lim = pv.share_change_bps.abs().max() * 1.25
    ax.set_xlim(-lim, lim)
    _title(fig, "Market share moved to Tata and Maruti; all four portfolio car brands gave share back",
           "Blue, bold: dealer-group franchise brands. Gray: other OEMs with at least 0.3% share.")
    path = IMG_DIR / "auto_share_change.png"
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path


def chart_ev_share(seg: pd.DataFrame) -> Path:
    """EV share of retail by month, 2026 vs the same month of 2025."""
    fig, ax = plt.subplots(figsize=(10, 4.8), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.07, right=0.88, top=0.80, bottom=0.14)
    labels = []  # (y, text, colour) for end-of-line labels
    for code, color, name in (("2W", ORANGE, "Two-wheelers"), ("PV", BLUE, "Cars")):
        s = seg[seg.segment == code]
        x = list(pd.to_datetime(s.month).dt.strftime("%b"))
        ax.plot(x, s.ev_share_2026_pct, color=color, linewidth=2, marker="o", markersize=5, label=f"{name}, 2026")
        ax.plot(x, s.ev_share_2025_pct, color=color, linewidth=1.4, linestyle=(0, (3, 2)), alpha=0.85,
                label=f"{name}, same month 2025")
        labels.append((s.ev_share_2026_pct.iloc[-1], f"{s.ev_share_2026_pct.iloc[-1]:.2f}%", INK))
        labels.append((s.ev_share_2025_pct.iloc[-1], f"{s.ev_share_2025_pct.iloc[-1]:.2f}%", INK_SOFT))
    # Nudge end labels apart so values that sit close together stay legible.
    labels.sort()
    placed: list[float] = []
    for y, text, color in labels:
        y_pos = max(y, placed[-1] + 0.75) if placed else y
        placed.append(y_pos)
        ax.text(len(x) - 1 + 0.18, y_pos, text, va="center", fontsize=9, color=color)
    ax.set_ylabel("EV share of retail (%)", color=MUTED, fontsize=9)
    ax.set_ylim(0, seg.ev_share_2026_pct.max() * 1.25)
    _style(ax)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left", ncol=2, frameon=False, fontsize=8.5, labelcolor=INK_SOFT)
    pv = seg[seg.segment == "PV"]
    _title(fig, f"EV share of car retail rose from {pv.ev_share_2026_pct.iloc[0]:.2f}% to "
                f"{pv.ev_share_2026_pct.iloc[-1]:.2f}% between February and September 2026",
           "Electric share of all-India retail by month. Solid: 2026. Dashed: same month of 2025.")
    path = IMG_DIR / "auto_ev_share.png"
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
    return path


# ----------------------------------------------------------------- brief --
def write_brief(perf: pd.DataFrame, monthly: pd.DataFrame, seg: pd.DataFrame,
                port: pd.DataFrame) -> Path:
    p = perf[perf.is_portfolio_brand].set_index("brand")
    pv_port = port[port.segment == "PV"].iloc[0]
    tw_seg = perf[perf.segment == "2W"].segment_growth_pct.iloc[0]
    pv_seg = pv_port.segment_growth_pct
    pv = perf[(perf.segment == "PV") & (perf.oem != "Others")]
    gainers = pv.nlargest(2, "share_change_bps")
    lux = perf[perf.brand.isin(["Mercedes-Benz", "BMW", "JLR"])].set_index("brand")
    evs = seg.set_index(["segment", "month"])
    pv_ev = seg[seg.segment == "PV"]
    tw_ev = seg[seg.segment == "2W"]
    sep = monthly[(monthly.month == "2026-09") & monthly.oem.isin(PORTFOLIO)].set_index("brand")

    def row(b: str) -> str:
        r = p.loc[b]
        growth = f"{r.yoy_growth_pct:+.2f}%" if abs(r.yoy_growth_pct) < 0.1 else f"{r.yoy_growth_pct:+.1f}%"
        return (f"| {b} | {SEGMENT_NAMES[r.segment]} | {r.units_2026:,.0f} | {growth} "
                f"| {r.segment_growth_pct:+.1f}% | {r.share_2025_pct:.2f}% → {r.share_2026_pct:.2f}% "
                f"| {r.share_change_bps:+.0f} |")

    lines = [
        "# Auto Retail Market Brief: Portfolio Brand Performance",
        "",
        "**Perspective:** a multi-brand dealer group holding Toyota, Honda Cars, JSW MG Motor and Mercedes-Benz "
        "car franchises and an Ather two-wheeler franchise.  ",
        "**Data:** FADA monthly vehicle retail (registration) data, February–September 2026 against the same "
        "months of 2025, all-India. Every figure below is computed by `python/auto_retail_analysis.py`.",
        "",
        "## Bottom line",
        "",
        f"The car market grew **{pv_seg:+.1f}%**, but the four portfolio car brands together grew only "
        f"**{pv_port.yoy_growth_pct:+.1f}%**. Their combined share fell from {pv_port.share_2025_pct:.2f}% to "
        f"{pv_port.share_2026_pct:.2f}% ({pv_port.share_change_bps:+.0f} bps). Had they simply held share, they "
        f"would have retailed about **{-pv_port.units_gap_vs_held_share:,.0f} more cars** nationally over eight months. "
        f"Ather is the opposite case: **{p.loc['Ather'].yoy_growth_pct:+.1f}%** growth against a "
        f"{tw_seg:+.1f}% two-wheeler market.",
        "",
        "## Brand scorecard",
        "",
        "| Brand | Segment | Units Feb–Sep 2026 | YoY growth | Segment growth | Market share | Share change (bps) |",
        "|---|---|---:|---:|---:|---|---:|",
        *[row(b) for b in ["Toyota", "MG Motor", "Honda Cars", "Mercedes-Benz", "Ather"]],
        "",
        "## Findings",
        "",
        f"1. **Share is moving to mass-market leaders.** {gainers.iloc[0].brand} gained "
        f"{gainers.iloc[0].share_change_bps:+.0f} bps and {gainers.iloc[1].brand} {gainers.iloc[1].share_change_bps:+.0f} bps. "
        f"Toyota, the largest portfolio brand, lost the most among portfolio brands "
        f"({p.loc['Toyota'].share_change_bps:+.0f} bps) despite growing {p.loc['Toyota'].yoy_growth_pct:+.1f}% in units.",
        f"2. **Luxury is flat for the portfolio brand, not for the segment.** Mercedes-Benz units were "
        f"{p.loc['Mercedes-Benz'].yoy_growth_pct:+.2f}% (flat: {p.loc['Mercedes-Benz'].units_2026:,.0f} vs {p.loc['Mercedes-Benz'].units_2025:,.0f}) while BMW grew {lux.loc['BMW'].yoy_growth_pct:+.1f}%.",
        f"3. **September shows a turn.** In September alone, Toyota grew {sep.loc['Toyota'].yoy_growth_pct:+.1f}%, "
        f"Honda Cars {sep.loc['Honda Cars'].yoy_growth_pct:+.1f}% and Mercedes-Benz "
        f"{sep.loc['Mercedes-Benz'].yoy_growth_pct:+.1f}% year on year. One month is not a trend; it is a reason "
        f"to have stock and sales capacity ready for the festive quarter.",
        f"4. **Electrification is accelerating.** EV share of car retail rose from {pv_ev.ev_share_2026_pct.iloc[0]:.2f}% "
        f"(Feb) to {pv_ev.ev_share_2026_pct.iloc[-1]:.2f}% (Sep), and of two-wheelers from "
        f"{tw_ev.ev_share_2026_pct.iloc[0]:.2f}% to {tw_ev.ev_share_2026_pct.iloc[-1]:.2f}%. "
        f"Ather is an EV-only brand, so its franchise rides this shift directly.",
        "",
        "## Recommendations for the dealer group",
        "",
        "1. **Treat Ather as the growth engine.** Prioritise working capital, outlet expansion and service capacity "
        "for the brand growing several times faster than its market.",
        "2. **Defend car share locally with conversion, not volume pushes.** National share loss means each walk-in "
        "matters more: track enquiry → test drive → booking → delivery conversion weekly by showroom "
        "(see the dealership KPI framework in `reports/auto_retail/DEALERSHIP_KPI_FRAMEWORK.md`).",
        "3. **Tighten inventory for slower brands.** Where a brand grows below market, keep days-in-stock and "
        "ageing (60+ day) stock under weekly review to limit holding cost.",
        "4. **Prepare for the festive quarter.** September's rebound across Toyota, Honda Cars and Mercedes-Benz "
        "supports stocking fast-moving variants ahead of October–November.",
        "",
        "## Limits of this analysis",
        "",
        "- National data only. FADA does not publish OEM-by-state splits, so this does not show performance in any "
        "specific state; a dealer would overlay its own showroom data.",
        "- Registrations (retail), not wholesale dispatches. They measure customer deliveries, the number a dealer "
        "is judged on.",
        "- Eight months. Compare the same months year on year, as done here, to avoid seasonal distortion.",
        "- Altigreen (electric three-wheeler cargo) does not appear individually in FADA's tables, so it is not analysed.",
        "",
        "## Charts",
        "",
        "![Growth vs market](../../screenshots/auto_growth_vs_market.png)",
        "",
        "![Share change](../../screenshots/auto_share_change.png)",
        "",
        "![EV share](../../screenshots/auto_ev_share.png)",
        "",
    ]
    path = OUT_DIR / "AUTO_RETAIL_BRIEF.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> None:
    oem, tot, ev = load()
    validate(oem, tot)
    perf = brand_performance(oem, tot)
    monthly = brand_monthly(oem, tot)
    seg = segment_monthly(tot, ev)
    port = portfolio_summary(perf)

    perf.round(4).to_csv(OUT_DIR / "brand_performance.csv", index=False)
    monthly.round(4).to_csv(OUT_DIR / "brand_monthly.csv", index=False)
    seg.round(4).to_csv(OUT_DIR / "segment_monthly.csv", index=False)
    port.round(4).to_csv(OUT_DIR / "portfolio_summary.csv", index=False)

    for path in (chart_growth_vs_market(perf), chart_share_change(perf), chart_ev_share(seg)):
        logger.info("Chart written: %s", path.relative_to(BASE_DIR))
    logger.info("Brief written: %s", write_brief(perf, monthly, seg, port).relative_to(BASE_DIR))


if __name__ == "__main__":
    main()
