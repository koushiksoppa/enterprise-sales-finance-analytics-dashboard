"""
report_theme.py
---------------
The single source of truth for how generated deliverables look and how
numbers are formatted.

The palette here is the same one encoded in `powerbi/theme.json`, so the HTML
executive report, the dashboard previews, and the Power BI report render the
same colours for the same meanings. Change a value here and in theme.json
together.

Not executable on its own - imported by generate_insights.py and
build_dashboard_previews.py.
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------- palette --

# Structural
INK = "#10243E"          # primary navy - headings, primary series, nav bar
INK_SOFT = "#1B3A5C"     # navy tint for secondary headings
TEXT = "#2E3A4B"         # body copy
MUTED = "#6B7A8D"        # labels, captions, axis text
BORDER = "#E3E8EF"       # hairlines, card outlines
SURFACE = "#FFFFFF"      # card background
CANVAS = "#F5F7FA"       # page background
SURFACE_ALT = "#EEF2F7"  # zebra rows, KPI card fill

# Sentiment - used only to encode good/bad, never for decoration
POSITIVE = "#1F7A54"
CAUTION = "#B0791C"
NEGATIVE = "#A93226"

# Categorical series, in the order Power BI assigns them
SERIES = [
    "#10243E",  # navy
    "#0F7C86",  # teal
    "#3E7CB1",  # steel blue
    "#6FA8A5",  # sage
    "#C08A2E",  # ochre
    "#7A6FA8",  # muted violet
    "#A85751",  # clay
    "#7A8794",  # slate
]

TEAL = SERIES[1]

FONT_STACK = "Segoe UI, -apple-system, BlinkMacSystemFont, Helvetica Neue, Arial, sans-serif"

# Margin bands. The same thresholds drive the `Margin Status` DAX measure, so
# a product flagged "At Risk" in the report is flagged "At Risk" in Power BI.
MARGIN_HEALTHY = 35.0
MARGIN_WATCH = 20.0


def margin_status(margin_pct: float) -> str:
    """Classify a margin percentage into the shared health bands."""
    if margin_pct >= MARGIN_HEALTHY:
        return "Healthy"
    if margin_pct >= MARGIN_WATCH:
        return "Watch"
    return "At Risk"


def sentiment_color(value: float, higher_is_better: bool = True) -> str:
    """Colour for a signed change. Neutral text colour when flat."""
    if value is None or (isinstance(value, float) and math.isnan(value)) or value == 0:
        return MUTED
    good = value > 0 if higher_is_better else value < 0
    return POSITIVE if good else NEGATIVE


# -------------------------------------------------------------- formatting --

def money(value: float, decimals: int = 0) -> str:
    """Full currency, e.g. $103,116,815."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    return f"${value:,.{decimals}f}"


def money_compact(value: float) -> str:
    """Headline currency, e.g. $103.1M - for KPI cards and axis labels."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    magnitude = abs(value)
    if magnitude >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if magnitude >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if magnitude >= 100_000:
        return f"${value / 1_000:.0f}K"
    # Below six figures, abbreviating costs more precision than it saves space:
    # an average order value reads as $5,244, never as $5K.
    return f"${value:,.0f}"


def number(value: float) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    return f"{value:,.0f}"


def percent(value: float, decimals: int = 1) -> str:
    """Percentage from a value already expressed in percent units."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    return f"{value:.{decimals}f}%"


def signed_percent(value: float, decimals: int = 1) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    return f"{value:+.{decimals}f}%"


def ratio(value: float, decimals: int = 2) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "n/a"
    return f"{value:.{decimals}f}x"


def format_value(value: float, fmt: str) -> str:
    """Format according to the `format` column of kpi_executive_summary.csv."""
    return {
        "currency": money,
        "percent": percent,
        "integer": number,
        "ratio": ratio,
    }.get(fmt, number)(value)


def format_value_compact(value: float, fmt: str) -> str:
    """Card-sized variant of format_value, for headline tiles."""
    if fmt == "currency":
        return money_compact(value)
    return format_value(value, fmt)


def month_label(period: str) -> str:
    """'2024-11' -> 'Nov 2024'."""
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    year, month = period.split("-")
    return f"{months[int(month) - 1]} {year}"
