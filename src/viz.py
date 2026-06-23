"""
viz.py
======
Shared presentation layer: one colour palette and one set of number formatters,
imported by both the notebook and the Streamlit app so the visual identity and
labels stay consistent across deliverables.
"""

from __future__ import annotations

# --- Category colour identity ------------------------------------------------ #
COLOR_BIKES = "#2E86AB"      # deep blue   -> revenue engine
COLOR_ACCESS = "#F6AE2D"     # amber       -> margin engine
COLOR_CLOTHING = "#E15554"   # coral red   -> support line

CATEGORY_COLORS = {
    "Bikes": COLOR_BIKES,
    "Accessories": COLOR_ACCESS,
    "Clothing": COLOR_CLOTHING,
}

# Sequential / accent colours for non-category charts
INK = "#22333B"              # axis text / dark
ACCENT = "#2E86AB"
ACCENT_2 = "#F6AE2D"
MUTED = "#9DB4C0"
GENDER_COLORS = {"M": "#2E86AB", "F": "#E15554"}

# A 6-step ordered sequence (used for countries / ranked bars)
SEQ6 = ["#0B3954", "#2E86AB", "#5BA4C9", "#87BDD8", "#B8D8E8", "#DCEAF2"]


# --- Number formatters ------------------------------------------------------- #
def money(x: float, decimals: int = 0) -> str:
    """$1,234,567 style."""
    return f"${x:,.{decimals}f}"


def money_compact(x: float) -> str:
    """$1.2M / $34.5K style for tight axis labels and KPI cards."""
    ax = abs(x)
    if ax >= 1_000_000_000:
        return f"${x/1_000_000_000:.1f}B"
    if ax >= 1_000_000:
        return f"${x/1_000_000:.1f}M"
    if ax >= 1_000:
        return f"${x/1_000:.0f}K"
    return f"${x:,.0f}"


def pct(x: float, decimals: int = 1) -> str:
    return f"{x:.{decimals}f}%"


def num_compact(x: float) -> str:
    ax = abs(x)
    if ax >= 1_000_000:
        return f"{x/1_000_000:.1f}M"
    if ax >= 1_000:
        return f"{x/1_000:.0f}K"
    return f"{x:,.0f}"
