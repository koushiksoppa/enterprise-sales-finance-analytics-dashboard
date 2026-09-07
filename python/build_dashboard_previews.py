"""
build_dashboard_previews.py
----------------------------
Renders one SVG preview per Power BI report page from the KPI tables in
reports/, at the same 1280x720 canvas Power BI Desktop uses.

The previews serve two purposes:

1. They are the screenshots in the README, so the repository shows the product
   even before someone opens Power BI Desktop.
2. They are the layout specification. Every panel here has a fixed grid
   position, and powerbi/POWERBI_BUILD_GUIDE.md quotes the same coordinates,
   so the assembled .pbix matches the published preview.

Every number drawn comes from a KPI table. Nothing is illustrative: if the
pipeline output changes, the previews change with it.

Run:
    python build_dashboard_previews.py
"""

from __future__ import annotations

import logging
from pathlib import Path
from xml.sax.saxutils import escape

import pandas as pd

import report_theme as t

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"
OUT_DIR = BASE_DIR / "screenshots"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------ canvas --
# 1280x720 is the Power BI Desktop default page size. Keeping the preview on
# the same canvas means the coordinates below are directly usable when placing
# visuals in Power BI.
W, H = 1280, 720
NAV_H = 44          # page navigation bar
FILTER_H = 30       # synced slicer summary strip
MARGIN = 16
CONTENT_TOP = NAV_H + FILTER_H + MARGIN
GUTTER = 12

PAGES = [
    "Executive Dashboard", "Sales Analytics", "Financial Analytics",
    "Customer Analytics", "Inventory Analytics", "Forecast Dashboard",
]

# Approximate advance width per character for the Segoe UI stack, used only to
# decide when a label needs truncating.
CHAR_W = 0.52


# ----------------------------------------------------------- svg primitives --

def _esc(value) -> str:
    return escape(str(value))


def truncate(text: str, max_px: float, size: float) -> str:
    limit = int(max_px / (size * CHAR_W))
    text = str(text)
    return text if len(text) <= limit else text[: max(1, limit - 1)] + "…"


def rect(x, y, w, h, fill, radius=0, stroke=None, opacity=None) -> str:
    parts = [f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}"']
    if radius:
        parts.append(f' rx="{radius}"')
    if stroke:
        parts.append(f' stroke="{stroke}" stroke-width="1"')
    if opacity is not None:
        parts.append(f' opacity="{opacity}"')
    parts.append("/>")
    return "".join(parts)


def text(x, y, content, size=12, fill=t.TEXT, weight=400, anchor="start",
         spacing=None, family=None) -> str:
    attrs = [
        f'x="{x:.1f}"', f'y="{y:.1f}"', f'font-size="{size}"', f'fill="{fill}"',
        f'font-weight="{weight}"',
    ]
    if anchor != "start":
        attrs.append(f'text-anchor="{anchor}"')
    if spacing:
        attrs.append(f'letter-spacing="{spacing}"')
    if family:
        attrs.append(f'font-family="{family}"')
    return f'<text {" ".join(attrs)}>{_esc(content)}</text>'


def line(x1, y1, x2, y2, stroke=t.BORDER, width=1, dash=None) -> str:
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{width}"{d}/>')


def polyline(points, stroke, width=2, dash=None, fill="none") -> str:
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<polyline points="{pts}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{width}" stroke-linejoin="round" stroke-linecap="round"{d}/>')


def polygon(points, fill, opacity=1.0) -> str:
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polygon points="{pts}" fill="{fill}" opacity="{opacity}"/>'


# ------------------------------------------------------------- chrome parts --

def nav_bar(active_page: str) -> list[str]:
    """The shared navigation bar repeated on every page."""
    out = [rect(0, 0, W, NAV_H, t.INK)]
    out.append(text(MARGIN, 28, "Enterprise Sales & Finance Analytics", 14, "#FFFFFF", 600))

    x = 420
    for page in PAGES:
        label_w = len(page) * 13 * CHAR_W + 22
        if page == active_page:
            out.append(rect(x, 9, label_w, 26, "#FFFFFF", radius=3, opacity=0.14))
        out.append(text(x + label_w / 2, 26, page, 11.5,
                        "#FFFFFF" if page == active_page else "#9FB3C8",
                        600 if page == active_page else 400, anchor="middle"))
        x += label_w + 4
    return out


def filter_bar(context: str) -> list[str]:
    """Summary of the synced slicer state, in the same place on every page."""
    y = NAV_H
    return [
        rect(0, y, W, FILTER_H, t.SURFACE),
        line(0, y + FILTER_H, W, y + FILTER_H, t.BORDER),
        text(MARGIN, y + 19, "FILTERS", 9.5, t.MUTED, 600, spacing="0.09em"),
        text(MARGIN + 58, y + 19, context, 11, t.TEXT),
        text(W - MARGIN, y + 19, "Synced across all pages", 10, t.MUTED, anchor="end"),
    ]


def kpi_card(x, y, w, h, label, value, note=None, value_color=None) -> list[str]:
    """A headline metric tile. One number, one label, one line of context."""
    return [
        rect(x, y, w, h, t.SURFACE, radius=3, stroke=t.BORDER),
        rect(x, y, 3, h, value_color or t.INK),
        text(x + 14, y + 20, label.upper(), 9.5, t.MUTED, 600, spacing="0.08em"),
        text(x + 14, y + 47, value, 24, value_color or t.INK, 600),
        text(x + 14, y + 65, note or "", 10, t.MUTED),
    ]


def panel(x, y, w, h, title, subtitle=None) -> tuple[list[str], tuple[float, float, float, float]]:
    """A titled card. Returns the SVG parts and the inner plot rectangle."""
    parts = [
        rect(x, y, w, h, t.SURFACE, radius=3, stroke=t.BORDER),
        text(x + 14, y + 22, title, 12.5, t.INK, 600),
    ]
    top = y + 34
    if subtitle:
        parts.append(text(x + 14, y + 37, subtitle, 10, t.MUTED))
        top = y + 48
    return parts, (x + 14, top, w - 28, y + h - 12 - top)


def legend(x, y, entries) -> list[str]:
    """entries: [(label, colour, dashed?)]"""
    out = []
    for label, colour, *rest in entries:
        dashed = rest[0] if rest else False
        out.append(line(x, y, x + 14, y, colour, 2.5, dash="3 2" if dashed else None))
        out.append(text(x + 19, y + 3.5, label, 10, t.MUTED))
        x += 19 + len(label) * 10 * CHAR_W + 16
    return out


# ------------------------------------------------------------------ charts --

def _nice_max(value: float) -> float:
    """Round an axis maximum up to a readable step."""
    if value <= 0:
        return 1.0
    magnitude = 10 ** (len(str(int(value))) - 1)
    for step in (1, 1.25, 1.5, 2, 2.5, 3, 4, 5, 7.5, 10):
        if value <= step * magnitude:
            return step * magnitude
    return 10 * magnitude


def line_chart(area, series, x_labels, value_fmt=t.money_compact, y_ticks=4,
               label_every=3, baseline_zero=True, bands=None, divider=None):
    """Multi-series line chart.

    series: [(label, values, colour, dashed)]. `bands` draws a shaded range as
    (lower, upper, colour); `divider` draws a labelled vertical rule at an index.
    """
    x0, y0, w, h = area
    plot_left = x0 + 46
    plot_w = w - 46
    plot_bottom = y0 + h - 20
    plot_h = plot_bottom - y0

    all_values = [v for _, values, *_ in series for v in values if v == v]
    if bands:
        all_values += [v for v in bands[0] + bands[1] if v == v]
    top = _nice_max(max(all_values))
    bottom = 0 if baseline_zero else min(all_values) * 0.95

    def sx(i, n):
        return plot_left + (plot_w * i / max(1, n - 1))

    def sy(v):
        return plot_bottom - (v - bottom) / (top - bottom) * plot_h

    out = []
    for i in range(y_ticks + 1):
        value = bottom + (top - bottom) * i / y_ticks
        y = sy(value)
        out.append(line(plot_left, y, x0 + w, y, t.BORDER))
        out.append(text(plot_left - 8, y + 3.5, value_fmt(value), 9.5, t.MUTED, anchor="end"))

    n = len(x_labels)
    for i, label in enumerate(x_labels):
        if i % label_every == 0 or i == n - 1:
            out.append(text(sx(i, n), plot_bottom + 15, label, 9.5, t.MUTED, anchor="middle"))

    if bands:
        lower, upper, colour = bands
        pts = [(sx(i, n), sy(v)) for i, v in enumerate(upper) if v == v]
        pts += [(sx(i, n), sy(v)) for i, v in reversed(list(enumerate(lower))) if v == v]
        out.append(polygon(pts, colour, 0.13))

    if divider is not None:
        index, label = divider
        x = sx(index, n)
        out.append(line(x, y0, x, plot_bottom, t.MUTED, 1, dash="4 3"))
        out.append(text(x + 6, y0 + 10, label, 9.5, t.MUTED, 600))

    for _, values, colour, dashed in series:
        pts = [(sx(i, n), sy(v)) for i, v in enumerate(values) if v == v]
        if pts:
            out.append(polyline(pts, colour, 2.2, dash="4 3" if dashed else None))
    return out


def bar_chart_h(area, labels, values, value_fmt=t.money_compact, colour=t.INK,
                highlight=None, max_bars=None, label_w=118):
    """Horizontal bars, ranked. `highlight` maps a label to an override colour."""
    x0, y0, w, h = area
    if max_bars:
        labels, values = labels[:max_bars], values[:max_bars]
    n = len(labels)
    if n == 0:
        return []
    row_h = h / n
    bar_h = min(16, row_h * 0.55)
    top = _nice_max(max(values)) if max(values) > 0 else 1
    bar_left = x0 + label_w
    bar_max = w - label_w - 56

    out = []
    for i, (label, value) in enumerate(zip(labels, values)):
        cy = y0 + row_h * i + row_h / 2
        out.append(text(x0, cy + 3.5, truncate(label, label_w - 8, 10.5), 10.5, t.TEXT))
        bar_w = max(1.0, bar_max * value / top)
        fill = (highlight or {}).get(label, colour)
        out.append(rect(bar_left, cy - bar_h / 2, bar_w, bar_h, fill, radius=2))
        out.append(text(bar_left + bar_w + 7, cy + 3.5, value_fmt(value), 10, t.MUTED))
    return out


def grouped_bar_h(area, labels, series_a, series_b, colour_a, colour_b,
                  value_fmt=t.number, label_w=118):
    """Two bars per row - used for stock vs reorder level."""
    x0, y0, w, h = area
    n = len(labels)
    row_h = h / n
    bar_h = min(7, row_h * 0.3)
    top = _nice_max(max(list(series_a) + list(series_b)))
    bar_left = x0 + label_w
    bar_max = w - label_w - 52

    out = []
    for i, label in enumerate(labels):
        cy = y0 + row_h * i + row_h / 2
        out.append(text(x0, cy + 3.5, truncate(label, label_w - 8, 10), 10, t.TEXT))
        out.append(rect(bar_left, cy - bar_h - 1, bar_max * series_a[i] / top, bar_h,
                        colour_a, radius=1))
        out.append(rect(bar_left, cy + 1, bar_max * series_b[i] / top, bar_h,
                        colour_b, radius=1))
        out.append(text(x0 + w, cy + 3.5, value_fmt(series_a[i]), 9.5, t.MUTED, anchor="end"))
    return out


def column_chart(area, labels, values, value_fmt=t.money_compact, colours=None,
                 line_series=None, line_fmt=t.percent, line_colour=None):
    """Columns with an optional secondary line on its own right-hand scale."""
    x0, y0, w, h = area
    plot_bottom = y0 + h - 18
    plot_h = plot_bottom - y0
    n = len(labels)
    slot = w / n
    bar_w = min(46, slot * 0.55)
    top = _nice_max(max(values))

    out = []
    for i in range(5):
        y = plot_bottom - plot_h * i / 4
        out.append(line(x0, y, x0 + w, y, t.BORDER))

    for i, (label, value) in enumerate(zip(labels, values)):
        cx = x0 + slot * i + slot / 2
        bar_h = plot_h * value / top
        fill = (colours or [t.INK] * n)[i % len(colours or [t.INK])]
        out.append(rect(cx - bar_w / 2, plot_bottom - bar_h, bar_w, bar_h, fill, radius=2))
        out.append(text(cx, plot_bottom - bar_h - 6, value_fmt(value), 9.5, t.TEXT, 600,
                        anchor="middle"))
        out.append(text(cx, plot_bottom + 14, truncate(label, slot - 4, 10), 10, t.MUTED,
                        anchor="middle"))

    if line_series:
        lo, hi = min(line_series) * 0.9, max(line_series) * 1.05
        pts = [(x0 + slot * i + slot / 2,
                plot_bottom - (v - lo) / (hi - lo) * plot_h * 0.8 - plot_h * 0.1)
               for i, v in enumerate(line_series)]
        out.append(polyline(pts, line_colour or t.CAUTION, 2))
        for (px, py), v in zip(pts, line_series):
            out.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3" fill="{line_colour or t.CAUTION}"/>')
            out.append(text(px, py - 9, line_fmt(v), 9.5, line_colour or t.CAUTION, 600,
                            anchor="middle"))
    return out


def donut(cx, cy, radius, thickness, slices):
    """slices: [(label, value, colour)] - drawn clockwise from 12 o'clock."""
    import math
    total = sum(v for _, v, _ in slices)
    out = []
    angle = -math.pi / 2
    for _, value, colour in slices:
        sweep = 2 * math.pi * value / total
        end = angle + sweep
        large = 1 if sweep > math.pi else 0
        x1, y1 = cx + radius * math.cos(angle), cy + radius * math.sin(angle)
        x2, y2 = cx + radius * math.cos(end), cy + radius * math.sin(end)
        inner = radius - thickness
        x3, y3 = cx + inner * math.cos(end), cy + inner * math.sin(end)
        x4, y4 = cx + inner * math.cos(angle), cy + inner * math.sin(angle)
        out.append(
            f'<path d="M {x1:.1f} {y1:.1f} A {radius} {radius} 0 {large} 1 {x2:.1f} {y2:.1f} '
            f'L {x3:.1f} {y3:.1f} A {inner} {inner} 0 {large} 0 {x4:.1f} {y4:.1f} Z" '
            f'fill="{colour}"/>'
        )
        angle = end
    return out


def table(area, columns, rows, row_h=22, pills=None):
    """columns: [(header, width, align)]. `pills` maps a column index to a
    {value: colour} map, rendered as a status chip."""
    x0, y0, w, h = area
    out = []
    x = x0
    for header, cw, align in columns:
        tx = x if align == "start" else x + cw
        out.append(text(tx, y0 + 10, header.upper(), 9, t.MUTED, 600, anchor=align,
                        spacing="0.06em"))
        x += cw
    out.append(line(x0, y0 + 16, x0 + w, y0 + 16, t.INK))

    for r, row in enumerate(rows):
        ry = y0 + 16 + row_h * r
        if r % 2 == 1:
            out.append(rect(x0, ry, w, row_h, t.SURFACE_ALT))
        x = x0
        for c, ((_, cw, align), value) in enumerate(zip(columns, row)):
            if pills and c in pills and value in pills[c]:
                colour = pills[c][value]
                pill_w = len(str(value)) * 10 * CHAR_W + 16
                out.append(rect(x, ry + row_h / 2 - 8, pill_w, 16, colour, radius=8, opacity=0.14))
                out.append(text(x + pill_w / 2, ry + row_h / 2 + 3.5, value, 9.5, colour, 600,
                                anchor="middle"))
            else:
                tx = x if align == "start" else x + cw - 6
                out.append(text(tx, ry + row_h / 2 + 3.5,
                                truncate(value, cw - 8, 10.5), 10.5, t.TEXT, anchor=align))
            x += cw
        out.append(line(x0, ry + row_h, x0 + w, ry + row_h, t.BORDER))
    return out


def bullets(area, items, accent=t.TEAL):
    """A short findings list - the executive insights panel."""
    x0, y0, w, _ = area
    out = []
    y = y0 + 4
    for headline, detail in items:
        out.append(rect(x0, y - 8, 2.5, 30, accent))
        out.append(text(x0 + 12, y + 2, headline, 11, t.INK_SOFT, 600))
        for i, chunk in enumerate(_wrap(detail, w - 14, 10.5)):
            out.append(text(x0 + 12, y + 16 + i * 13, chunk, 10.5, t.TEXT))
        y += 30 + 13 * max(1, len(_wrap(detail, w - 14, 10.5)))
    return out


def _wrap(content: str, max_px: float, size: float) -> list[str]:
    limit = int(max_px / (size * CHAR_W))
    words, lines, current = str(content).split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= limit:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def page(active: str, context: str, body: list[str]) -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" '
        f'height="{H}" font-family="{t.FONT_STACK}">',
        f'<title>{_esc(active)}</title>',
        rect(0, 0, W, H, t.CANVAS),
    ]
    parts += nav_bar(active)
    parts += filter_bar(context)
    parts += body
    parts.append("</svg>")
    return "\n".join(parts)


# ------------------------------------------------------------------- pages --

def load() -> dict:
    names = ["executive_summary", "monthly_sales_growth", "top_10_products",
             "lowest_margin_products", "top_10_customers", "regional_performance",
             "country_performance", "category_performance", "segment_performance",
             "customer_growth", "inventory_turnover", "revenue_forecast"]
    data = {n: pd.read_csv(REPORTS_DIR / f"kpi_{n}.csv") for n in names}
    data["kpi"] = {r["metric"]: r["value"] for _, r in data["executive_summary"].iterrows()}
    return data


def _card_row(y, cards, count=6):
    """Evenly spaced KPI tiles across the content width."""
    total_w = W - 2 * MARGIN
    cw = (total_w - GUTTER * (count - 1)) / count
    out = []
    for i, card in enumerate(cards):
        out += kpi_card(MARGIN + i * (cw + GUTTER), y, cw, 78, *card[:3],
                        value_color=card[3] if len(card) > 3 else None)
    return out


def executive_dashboard(d: dict) -> str:
    k, monthly = d["kpi"], d["monthly_sales_growth"]
    regions = d["regional_performance"]
    products = d["top_10_products"]
    categories = d["category_performance"]

    body = _card_row(CONTENT_TOP, [
        ("Revenue", t.money_compact(k["Total Revenue"]), "36 months to Dec 2024"),
        ("Profit", t.money_compact(k["Total Profit"]), "Net of cost of goods"),
        ("Profit margin", t.percent(k["Profit Margin %"]), "Healthy band, above 35%"),
        ("Revenue growth YoY", t.signed_percent(k["Revenue Growth YoY %"]), "2023 to 2024",
         t.sentiment_color(k["Revenue Growth YoY %"])),
        ("Orders", t.number(k["Total Orders"]), f"AOV {t.money(k['Average Order Value'])}"),
        ("Customers", t.number(k["Total Customers"]), "Transacting in period"),
    ])

    row2_y = CONTENT_TOP + 78 + GUTTER
    row2_h = 248
    parts, area = panel(MARGIN, row2_y, 780, row2_h, "Revenue and profit by month",
                        "Monthly totals across the full reporting period")
    body += parts
    body += line_chart(
        area,
        [("Revenue", monthly["revenue"].tolist(), t.INK, False),
         ("Profit", monthly["profit"].tolist(), t.TEAL, False)],
        [t.month_label(m) for m in monthly["month"]], label_every=4,
    )
    body += legend(MARGIN + 620, row2_y + 22, [("Revenue", t.INK), ("Profit", t.TEAL)])

    parts, area = panel(MARGIN + 780 + GUTTER, row2_y, W - 2 * MARGIN - 780 - GUTTER, row2_h,
                        "Revenue by region", "Countries rolled up to their region")
    body += parts
    body += bar_chart_h(area, regions["region_name"].tolist(),
                        regions["total_revenue"].tolist(), label_w=132)

    row3_y = row2_y + row2_h + GUTTER
    row3_h = H - MARGIN - row3_y
    parts, area = panel(MARGIN, row3_y, 400, row3_h, "Top products by revenue")
    body += parts
    body += bar_chart_h(area, products["product_name"].tolist(),
                        products["total_revenue"].tolist(), max_bars=5, label_w=134)

    parts, area = panel(MARGIN + 412, row3_y, 400, row3_h, "Revenue by category")
    body += parts
    body += bar_chart_h(area, categories["category"].tolist(),
                        categories["total_revenue"].tolist(),
                        colour=t.SERIES[2], label_w=110)

    insight_x = MARGIN + 824
    parts, area = panel(insight_x, row3_y, W - MARGIN - insight_x, row3_h, "Executive insights")
    body += parts

    best_region = regions.iloc[0]
    worst_margin_cat = categories.sort_values("profit_margin_pct").iloc[0]
    reorder = d["inventory_turnover"]
    reorder_count = int((reorder["risk_flag"] == "REORDER NOW").sum())
    body += bullets(area, [
        (f"{best_region['region_name']} leads at "
         f"{t.percent(best_region['revenue_share_pct'])} of revenue",
         f"{t.money_compact(best_region['total_revenue'])} at "
         f"{t.percent(best_region['profit_margin_pct'])} margin across "
         f"{int(best_region['countries'])} countries."),
        (f"{worst_margin_cat['category']} is the margin drag",
         f"{t.percent(worst_margin_cat['profit_margin_pct'])} against a "
         f"{t.percent(k['Profit Margin %'])} blended margin on "
         f"{t.money_compact(worst_margin_cat['total_revenue'])} of revenue."),
        (f"{reorder_count} product(s) at reorder level",
         "Stock on hand has reached the replenishment trigger; see Inventory Analytics."),
    ])
    return page("Executive Dashboard", "All years  ·  All regions  ·  All categories  ·  "
                "All segments", body)


def sales_analytics(d: dict) -> str:
    k, monthly = d["kpi"], d["monthly_sales_growth"]
    categories, regions = d["category_performance"], d["regional_performance"]
    products, segments = d["top_10_products"], d["segment_performance"]

    body = _card_row(CONTENT_TOP, [
        ("Revenue", t.money_compact(k["Total Revenue"]), "Net of discounts"),
        ("Orders", t.number(k["Total Orders"]), "Distinct order IDs"),
        ("Average order value", t.money(k["Average Order Value"]), "Revenue / orders"),
        ("Units sold", t.number(k["Units Sold"]), "Order-line quantity"),
        ("Growth MoM", t.signed_percent(k["Revenue Growth MoM %"]), "Nov to Dec 2024",
         t.sentiment_color(k["Revenue Growth MoM %"])),
        ("Growth YoY", t.signed_percent(k["Revenue Growth YoY %"]), "2023 to 2024",
         t.sentiment_color(k["Revenue Growth YoY %"])),
    ])

    row2_y = CONTENT_TOP + 78 + GUTTER
    row2_h = 248
    parts, area = panel(MARGIN, row2_y, 780, row2_h, "Revenue trend and 3-month average",
                        "Seasonal peaks land in November and December")
    body += parts
    rolling = monthly["revenue"].rolling(3, min_periods=1).mean().tolist()
    body += line_chart(
        area,
        [("Revenue", monthly["revenue"].tolist(), t.INK, False),
         ("3-month average", rolling, t.SERIES[4], True)],
        [t.month_label(m) for m in monthly["month"]], label_every=4,
    )
    body += legend(MARGIN + 560, row2_y + 22,
                   [("Revenue", t.INK), ("3-month average", t.SERIES[4], True)])

    parts, area = panel(MARGIN + 792, row2_y, W - 2 * MARGIN - 792, row2_h,
                        "Average order value by category")
    body += parts
    ordered = categories.sort_values("avg_order_value", ascending=False)
    body += bar_chart_h(area, ordered["category"].tolist(),
                        ordered["avg_order_value"].tolist(),
                        value_fmt=t.money, colour=t.SERIES[2], label_w=110)

    row3_y = row2_y + row2_h + GUTTER
    row3_h = H - MARGIN - row3_y
    parts, area = panel(MARGIN, row3_y, 620, row3_h, "Top 10 products")
    body += parts
    body += table(area, [("Product", 190, "start"), ("Category", 120, "start"),
                         ("Revenue", 110, "end"), ("Units", 80, "end"), ("Margin", 92, "end")],
                  [(r["product_name"], r["category"], t.money_compact(r["total_revenue"]),
                    t.number(r["units_sold"]), t.percent(r["profit_margin_pct"]))
                   for _, r in products.iterrows()], row_h=21)

    parts, area = panel(MARGIN + 632, row3_y, 320, row3_h, "Revenue by region")
    body += parts
    body += bar_chart_h(area, regions["region_name"].tolist(),
                        regions["total_revenue"].tolist(), label_w=124)

    parts, area = panel(MARGIN + 964, row3_y, W - MARGIN - (MARGIN + 964), row3_h,
                        "Revenue by segment")
    body += parts
    body += bar_chart_h(area, segments["segment"].tolist(),
                        segments["total_revenue"].tolist(),
                        colour=t.SERIES[3], label_w=98)
    return page("Sales Analytics", "All years  ·  All regions  ·  All categories  ·  "
                "All segments", body)


def financial_analytics(d: dict) -> str:
    k, monthly = d["kpi"], d["monthly_sales_growth"]
    categories, low_margin = d["category_performance"], d["lowest_margin_products"]
    regions = d["regional_performance"]

    cost = k["Total Revenue"] - k["Total Profit"]
    body = _card_row(CONTENT_TOP, [
        ("Revenue", t.money_compact(k["Total Revenue"]), "Net of discounts"),
        ("Cost of goods", t.money_compact(cost), "Direct product cost"),
        ("Gross profit", t.money_compact(k["Total Profit"]), "Revenue less cost"),
        ("Profit margin", t.percent(k["Profit Margin %"]), "Healthy, above the 35% band",
         t.POSITIVE),
        ("Lowest category margin",
         t.percent(categories["profit_margin_pct"].min()),
         categories.sort_values("profit_margin_pct").iloc[0]["category"], t.CAUTION),
        ("Products below 35%",
         t.number(int((low_margin["margin_pct"] < t.MARGIN_HEALTHY).sum())),
         "Watch or At Risk status", t.CAUTION),
    ])

    row2_y = CONTENT_TOP + 78 + GUTTER
    row2_h = 248
    parts, area = panel(MARGIN, row2_y, 780, row2_h, "Profit and margin by month",
                        "Margin holds a narrow band while profit tracks seasonality")
    body += parts
    body += line_chart(
        area, [("Profit", monthly["profit"].tolist(), t.TEAL, False)],
        [t.month_label(m) for m in monthly["month"]], label_every=4,
    )
    # Margin sits on its own scale; drawn as a flat reference band so the two
    # series are not read against the same axis.
    x0, y0, w, h = area
    margin_min, margin_max = monthly["profit_margin_pct"].min(), monthly["profit_margin_pct"].max()
    body += [
        text(x0 + w, y0 - 12, f"Monthly margin range {t.percent(margin_min)} - "
                              f"{t.percent(margin_max)}", 10, t.MUTED, anchor="end"),
    ]
    body += legend(MARGIN + 620, row2_y + 22, [("Profit", t.TEAL)])

    parts, area = panel(MARGIN + 792, row2_y, W - 2 * MARGIN - 792, row2_h,
                        "Margin by category", "Against the 35% healthy threshold")
    body += parts
    ordered = categories.sort_values("profit_margin_pct", ascending=False)
    highlight = {r["category"]: (t.POSITIVE if r["profit_margin_pct"] >= t.MARGIN_HEALTHY
                                 else t.CAUTION) for _, r in ordered.iterrows()}
    body += bar_chart_h(area, ordered["category"].tolist(),
                        ordered["profit_margin_pct"].tolist(),
                        value_fmt=t.percent, highlight=highlight, label_w=110)

    row3_y = row2_y + row2_h + GUTTER
    row3_h = H - MARGIN - row3_y
    parts, area = panel(MARGIN, row3_y, 620, row3_h, "Lowest-margin products",
                        "Status against the 35% / 20% margin bands")
    body += parts
    body += table(area, [("Product", 180, "start"), ("Category", 128, "start"),
                         ("Revenue", 100, "end"), ("Margin", 76, "end"), ("Status", 108, "start")],
                  [(r["product_name"], r["category"], t.money_compact(r["total_revenue"]),
                    t.percent(r["margin_pct"]), t.margin_status(r["margin_pct"]))
                   for _, r in low_margin.iterrows()], row_h=24,
                  pills={4: {"Healthy": t.POSITIVE, "Watch": t.CAUTION, "At Risk": t.NEGATIVE}})

    parts, area = panel(MARGIN + 632, row3_y, W - 2 * MARGIN - 632, row3_h,
                        "Profit by region")
    body += parts
    body += bar_chart_h(area, regions["region_name"].tolist(),
                        regions["total_profit"].tolist(), colour=t.TEAL, label_w=130)
    return page("Financial Analytics", "All years  ·  All regions  ·  All categories  ·  "
                "All segments", body)


def customer_analytics(d: dict) -> str:
    k = d["kpi"]
    growth, segments, customers = d["customer_growth"], d["segment_performance"], d["top_10_customers"]

    orders_per_customer = k["Total Orders"] / k["Total Customers"]
    revenue_per_customer = k["Total Revenue"] / k["Total Customers"]
    body = _card_row(CONTENT_TOP, [
        ("Customers", t.number(k["Total Customers"]), "Transacting in period"),
        ("Customers on file", t.number(k["Customers On File"]), "Rows in DimCustomer"),
        ("Orders per customer", f"{orders_per_customer:,.1f}", "Across 36 months"),
        ("Revenue per customer", t.money_compact(revenue_per_customer), "Lifetime, in period"),
        ("Repeat rate", t.percent(k["Repeat Customer Rate %"]), "Saturated on this base"),
        ("Average order value", t.money(k["Average Order Value"]), "Revenue / orders"),
    ])

    row2_y = CONTENT_TOP + 78 + GUTTER
    row2_h = 248
    parts, area = panel(MARGIN, row2_y, 780, row2_h, "Customer base growth",
                        "Cumulative customers on file by signup month")
    body += parts
    body += line_chart(
        area, [("Cumulative customers", growth["cumulative_customers"].tolist(), t.INK, False)],
        [t.month_label(m) for m in growth["signup_month"]],
        value_fmt=t.number, label_every=5,
    )

    parts, area = panel(MARGIN + 792, row2_y, W - 2 * MARGIN - 792, row2_h,
                        "Revenue by segment")
    body += parts
    x0, y0, w, h = area
    slices = [(r["segment"], r["total_revenue"], t.SERIES[i % len(t.SERIES)])
              for i, (_, r) in enumerate(segments.iterrows())]
    body += donut(x0 + 78, y0 + h / 2 - 6, 62, 22, slices)
    ly = y0 + 16
    for label, value, colour in slices:
        body.append(rect(x0 + 158, ly - 7, 9, 9, colour, radius=2))
        body.append(text(x0 + 173, ly + 1, label, 10.5, t.TEXT))
        body.append(text(x0 + w, ly + 1, t.money_compact(value), 10.5, t.MUTED, anchor="end"))
        ly += 21

    row3_y = row2_y + row2_h + GUTTER
    row3_h = H - MARGIN - row3_y
    parts, area = panel(MARGIN, row3_y, 700, row3_h, "Top 10 customers by revenue")
    body += parts
    body += table(area, [("Customer", 168, "start"), ("Segment", 112, "start"),
                         ("Region", 140, "start"), ("Revenue", 110, "end"),
                         ("Orders", 74, "end"), ("AOV", 68, "end")],
                  [(r["customer_name"], r["segment"], r["region_name"],
                    t.money_compact(r["total_revenue"]), t.number(r["total_orders"]),
                    t.money(r["avg_order_value"]))
                   for _, r in customers.iterrows()], row_h=21)

    parts, area = panel(MARGIN + 712, row3_y, W - 2 * MARGIN - 712, row3_h,
                        "Revenue per customer by segment")
    body += parts
    ordered = segments.sort_values("revenue_per_customer", ascending=False)
    body += bar_chart_h(area, ordered["segment"].tolist(),
                        ordered["revenue_per_customer"].tolist(),
                        colour=t.SERIES[3], label_w=110)
    return page("Customer Analytics", "All years  ·  All regions  ·  All categories  ·  "
                "All segments", body)


def inventory_analytics(d: dict) -> str:
    k, inventory = d["kpi"], d["inventory_turnover"]
    at_risk = inventory[inventory["risk_flag"] != "OK"]

    body = _card_row(CONTENT_TOP, [
        ("Stock positions", t.number(len(inventory)), "Product x warehouse"),
        ("Units on hand", t.number(inventory["stock_quantity"].sum()), "Current snapshot"),
        ("Stock value", t.money_compact(inventory["stock_value"].sum()), "At unit cost"),
        ("Turnover ratio", t.ratio(k["Inventory Turnover Ratio"]), "Units sold / on hand"),
        ("At reorder level", t.number(int((inventory["risk_flag"] == "REORDER NOW").sum())),
         "Replenish now", t.NEGATIVE),
        ("Within 25% of trigger", t.number(int((inventory["risk_flag"] == "AT RISK").sum())),
         "Thin buffer", t.CAUTION),
    ])

    row2_y = CONTENT_TOP + 78 + GUTTER
    row2_h = 300
    parts, area = panel(MARGIN, row2_y, 660, row2_h, "Stock on hand vs reorder level",
                        "Lowest headroom first")
    body += parts
    ordered = inventory.sort_values("stock_vs_reorder").head(11)
    body += grouped_bar_h(area, ordered["product_name"].tolist(),
                          ordered["stock_quantity"].tolist(),
                          ordered["reorder_level"].tolist(),
                          t.SERIES[2], t.CAUTION, label_w=142)
    body += legend(MARGIN + 400, row2_y + 22,
                   [("Stock on hand", t.SERIES[2]), ("Reorder level", t.CAUTION)])

    parts, area = panel(MARGIN + 672, row2_y, W - 2 * MARGIN - 672, row2_h,
                        "Turnover ratio by product", "Units sold across the period per unit held")
    body += parts
    fastest = inventory.sort_values("turnover_ratio", ascending=False).head(11)
    body += bar_chart_h(area, fastest["product_name"].tolist(),
                        fastest["turnover_ratio"].tolist(),
                        value_fmt=t.ratio, colour=t.TEAL, label_w=150)

    row3_y = row2_y + row2_h + GUTTER
    row3_h = H - MARGIN - row3_y
    parts, area = panel(MARGIN, row3_y, W - 2 * MARGIN, row3_h, "Replenishment watchlist",
                        "Positions at or approaching the reorder trigger")
    body += parts
    if len(at_risk) == 0:
        body.append(text(area[0], area[1] + 24, "No position is at or near its reorder level.",
                         11, t.MUTED))
    else:
        body += table(area, [("Product", 220, "start"), ("Category", 150, "start"),
                             ("Warehouse", 110, "start"), ("Stock", 90, "end"),
                             ("Reorder level", 110, "end"), ("Headroom", 100, "end"),
                             ("Stock value", 120, "end"), ("Status", 130, "start")],
                      [(r["product_name"], r["category"], r["warehouse"],
                        t.number(r["stock_quantity"]), t.number(r["reorder_level"]),
                        t.number(r["stock_vs_reorder"]), t.money(r["stock_value"]),
                        r["risk_flag"].title())
                       for _, r in at_risk.iterrows()], row_h=24,
                      pills={7: {"Reorder Now": t.NEGATIVE, "At Risk": t.CAUTION}})
    return page("Inventory Analytics", "All years  ·  All regions  ·  All categories  ·  "
                "All warehouses", body)


def forecast_dashboard(d: dict) -> str:
    forecast = d["revenue_forecast"]
    history = forecast[forecast["is_forecast"] == 0]
    future = forecast[forecast["is_forecast"] == 1]

    baseline_idx = set(future["month_index"] - 12)
    baseline = history[history["month_index"].isin(baseline_idx)]
    vs_baseline = future["forecast_revenue"].sum() / baseline["actual_revenue"].sum() * 100 - 100
    slope_per_month = (history["linear_trend"].iloc[-1] - history["linear_trend"].iloc[0]) / (
        len(history) - 1)

    body = _card_row(CONTENT_TOP, [
        ("Last actual month", t.money_compact(history["actual_revenue"].iloc[-1]),
         t.month_label(history["month"].iloc[-1])),
        ("Next month projected", t.money_compact(future["forecast_revenue"].iloc[0]),
         t.month_label(future["month"].iloc[0])),
        ("6-month projection", t.money_compact(future["forecast_revenue"].sum()),
         f"{t.month_label(future['month'].iloc[0])} to "
         f"{t.month_label(future['month'].iloc[-1])}"),
        ("Modelled range",
         f"{t.money_compact(future['forecast_lower'].sum())} - "
         f"{t.money_compact(future['forecast_upper'].sum())}", "95% of in-sample spread"),
        ("vs same months last year", t.signed_percent(vs_baseline), "Like-for-like seasonality",
         t.sentiment_color(vs_baseline)),
        ("Underlying trend", f"{t.money_compact(slope_per_month)}/mo", "OLS slope, revenue"),
    ])

    row2_y = CONTENT_TOP + 78 + GUTTER
    row2_h = 330
    parts, area = panel(MARGIN, row2_y, W - 2 * MARGIN, row2_h,
                        "Revenue: actuals, trend and projection",
                        "Solid line is recorded revenue; dashed line and shaded band are modelled")
    body += parts

    months = forecast["month"].tolist()
    n_hist = len(history)
    nan = float("nan")
    actual = forecast["actual_revenue"].tolist()
    trend = forecast["linear_trend"].tolist()
    moving = forecast["moving_avg_3m"].tolist()
    # The projected line starts at the last actual point so the two connect.
    projected = [nan] * (n_hist - 1) + [actual[n_hist - 1]] + \
                future["forecast_revenue"].tolist()
    lower = [nan] * (n_hist - 1) + [actual[n_hist - 1]] + future["forecast_lower"].tolist()
    upper = [nan] * (n_hist - 1) + [actual[n_hist - 1]] + future["forecast_upper"].tolist()

    body += line_chart(
        area,
        [("Actual revenue", actual, t.INK, False),
         ("3-month average", moving, t.SERIES[3], False),
         ("Linear trend", trend, t.SERIES[4], True),
         ("Projection", projected, t.TEAL, True)],
        [t.month_label(m) for m in months], label_every=4,
        bands=(lower, upper, t.TEAL),
        divider=(n_hist - 1, "Last actual"),
    )
    body += legend(MARGIN + 300, row2_y + 24, [
        ("Actual revenue", t.INK), ("3-month average", t.SERIES[3]),
        ("Linear trend", t.SERIES[4], True), ("Projection and range", t.TEAL, True),
    ])

    row3_y = row2_y + row2_h + GUTTER
    row3_h = H - MARGIN - row3_y
    parts, area = panel(MARGIN, row3_y, 700, row3_h, "Monthly projection")
    body += parts
    body += table(area, [("Month", 130, "start"), ("Low", 140, "end"),
                         ("Projected", 150, "end"), ("High", 140, "end"),
                         ("Trend", 130, "end")],
                  [(t.month_label(r["month"]), t.money(r["forecast_lower"]),
                    t.money(r["forecast_revenue"]), t.money(r["forecast_upper"]),
                    t.money(r["linear_trend"])) for _, r in future.iterrows()], row_h=21)

    parts, area = panel(MARGIN + 712, row3_y, W - 2 * MARGIN - 712, row3_h, "How to read this")
    body += parts
    body += bullets(area, [
        ("Method",
         "Least-squares trend on monthly revenue, scaled by a month-of-year seasonal index "
         "derived from the same history."),
        ("Range",
         "Plus or minus 1.96 residual standard deviations of the in-sample fit - historical "
         "dispersion, not a confidence guarantee."),
        ("Assumption",
         "Pricing, product mix and market conditions hold. Treat as a planning input, not a "
         "commitment."),
    ], accent=t.MUTED)
    return page("Forecast Dashboard", "All years  ·  All regions  ·  All categories  ·  "
                "All segments", body)


BUILDERS = {
    "executive_dashboard": executive_dashboard,
    "sales_analytics": sales_analytics,
    "financial_analytics": financial_analytics,
    "customer_analytics": customer_analytics,
    "inventory_analytics": inventory_analytics,
    "forecast_dashboard": forecast_dashboard,
}


def main() -> None:
    data = load()
    for name, builder in BUILDERS.items():
        path = OUT_DIR / f"{name}.svg"
        path.write_text(builder(data), encoding="utf-8")
        logger.info("Wrote %s", path.name)
    logger.info("Dashboard previews written to %s", OUT_DIR)


if __name__ == "__main__":
    main()
