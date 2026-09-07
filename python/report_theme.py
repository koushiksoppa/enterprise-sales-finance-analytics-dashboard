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


class Tone(str):
    """A colour that also knows its dark-mode counterpart and CSS token name.

    It subclasses `str` and carries the light hex, so every consumer that just
    wants a colour string keeps working unchanged. The SVG writer additionally
    reads `.token` to tag the element with a class, which the embedded
    stylesheet then re-colours under `prefers-color-scheme: dark`.
    """

    __slots__ = ("dark", "token")

    def __new__(cls, light: str, dark: str, token: str) -> "Tone":
        obj = super().__new__(cls, light)
        obj.dark = dark
        obj.token = token
        return obj


TONES: list[Tone] = []


def _tone(light: str, dark: str, token: str) -> Tone:
    tone = Tone(light, dark, token)
    TONES.append(tone)
    return tone


# Structural. Dark values target a neutral slate ground rather than pure black,
# which keeps the card edges visible without a heavy border.
CANVAS = _tone("#F5F7FA", "#0D1117", "canvas")        # page background
SURFACE = _tone("#FFFFFF", "#161B22", "surface")      # card background
SURFACE_ALT = _tone("#EEF2F7", "#1C2430", "surfaceAlt")  # zebra rows
BORDER = _tone("#E3E8EF", "#30363D", "border")        # hairlines, card outlines

# Type. INK is the strongest text colour, NOT a chart colour - in dark mode
# text has to invert to near-white while the navy series has to brighten to a
# legible blue instead. Conflating the two is what makes a naive dark variant
# render invisible bars.
INK = _tone("#10243E", "#E6EDF3", "ink")              # headings, KPI values
INK_SOFT = _tone("#1B3A5C", "#C6D3E1", "inkSoft")     # secondary headings
TEXT = _tone("#2E3A4B", "#BAC5D2", "text")            # body copy
MUTED = _tone("#6B7A8D", "#8B98A8", "muted")          # labels, axis text

# Navigation chrome keeps the brand navy in both themes so the bar stays
# recognisable; only its depth changes.
NAV = _tone("#10243E", "#152233", "nav")
ON_NAV = _tone("#FFFFFF", "#E6EDF3", "onNav")
NAV_MUTED = _tone("#9FB3C8", "#8095AC", "navMuted")

# Sentiment - used only to encode good/bad, never for decoration
POSITIVE = _tone("#1F7A54", "#46B37F", "positive")
CAUTION = _tone("#B0791C", "#D3A03A", "caution")
NEGATIVE = _tone("#A93226", "#E06C60", "negative")

# Categorical series, in the order Power BI assigns them. Dark counterparts are
# lifted in lightness and dropped in saturation so they read against the dark
# ground at the same visual weight they carry on white.
SERIES = [
    _tone("#10243E", "#7FB0E0", "series0"),  # navy      -> soft blue
    _tone("#0F7C86", "#3FB8C4", "series1"),  # teal
    _tone("#3E7CB1", "#6FA8DC", "series2"),  # steel blue
    _tone("#6FA8A5", "#86C3BF", "series3"),  # sage
    _tone("#C08A2E", "#D9A94A", "series4"),  # ochre
    _tone("#7A6FA8", "#A99BD6", "series5"),  # muted violet
    _tone("#A85751", "#D08983", "series6"),  # clay
    _tone("#7A8794", "#9AA7B4", "series7"),  # slate
]

TEAL = SERIES[1]
PRIMARY = SERIES[0]  # the primary chart series - not the same thing as INK

# Multi-word family names are quoted: unquoted works in every current browser
# but is fragile in stricter SVG consumers (Inkscape, some PDF converters).
FONT_STACK = ("'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', "
              "Arial, sans-serif")

# Margin bands. The same thresholds drive the `Margin Status` DAX measure, so
# a product flagged "At Risk" in the report is flagged "At Risk" in Power BI.
MARGIN_HEALTHY = 35.0
MARGIN_WATCH = 20.0


def dark_mode_css(indent: str = "  ") -> str:
    """CSS that recolours tagged SVG elements under a dark UA preference.

    Every element keeps its light colour as a presentation attribute and gains
    a class; a CSS rule outranks a presentation attribute, so these override
    cleanly. If a consumer strips `<style>` the file still renders correctly in
    light — the dark variant degrades to the previous behaviour rather than
    breaking.

    Note this follows the reader's OS/browser colour-scheme preference, which
    is not necessarily the same as a site's own light/dark toggle.
    """
    rules = []
    for tone in TONES:
        rules.append(f"{indent}  .f-{tone.token}{{fill:{tone.dark}}}")
        rules.append(f"{indent}  .s-{tone.token}{{stroke:{tone.dark}}}")
    return f"{indent}@media (prefers-color-scheme: dark) {{\n" + "\n".join(rules) + f"\n{indent}}}"


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
