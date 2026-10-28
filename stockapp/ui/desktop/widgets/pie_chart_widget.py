"""
Pie chart for the portfolio's allocation by market value. Same
matplotlib-in-Qt pattern as chart_widget.py, kept as a separate widget since
it has nothing to do with the price timeline.
"""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.colors import to_rgb
from matplotlib.figure import Figure

# Fixed, visually distinct palette so a given slot's color stays stable across
# refreshes — matplotlib's default cycle only has 10 colors before repeating.
_PALETTE = [
    "#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F",
    "#EDC948", "#B07AA1", "#FF9DA7", "#9C755F", "#BAB0AC",
    "#86BCB6", "#D37295", "#FABFD2", "#B6992D", "#499894",
]

# Slices smaller than this get no in-slice percentage (the legend still has it).
_MIN_INLINE_PCT = 5.0

# Dark slice borders stay visible against both the white background and the
# light slice colors, unlike white ones.
_EDGE_COLOR = "#1f1f1f"


def _text_color_for(fill: str) -> str:
    """Black on light fills, white on dark ones (WCAG relative luminance)."""
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in to_rgb(fill))
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    # Black and white contrast equally at L≈0.179. Default to black: only
    # fills clearly darker than that tie point get white text.
    return "black" if luminance > 0.15 else "white"
    #maybe remove, and default to black


class PortfolioPieChartWidget(FigureCanvasQTAgg):
    def __init__(self):
        self._figure = Figure(figsize=(5, 4))
        super().__init__(self._figure)
        self._ax = self._figure.add_subplot(111)

    def plot_distribution(self, percentages: dict[str, float]) -> None:
        """percentages: label -> % of portfolio (0-100), e.g. from
        analysis.portfolio_analysis.compute_distribution."""
        self._ax.clear()
        if not percentages:
            self._ax.set_title("No portfolio value to show yet")
            self.draw()
            return

        labels = list(percentages.keys())
        values = list(percentages.values())
        colors = [_PALETTE[i % len(_PALETTE)] for i in range(len(labels))]

        # Labels live in a legend rather than on the rim: rim labels collide
        # as soon as a few small slices sit next to each other. Percentages
        # are drawn inside a slice only when it's big enough to hold them.
        wedges, _texts, autotexts = self._ax.pie(
            values,
            colors=colors,
            startangle=90,
            counterclock=False,
            autopct=lambda pct: f"{pct:.1f}%" if pct >= _MIN_INLINE_PCT else "",
            pctdistance=0.7,
            textprops={"fontsize": 10, "fontweight": "bold"},
            wedgeprops={"linewidth": 1.5, "edgecolor": _EDGE_COLOR},
        )
        # Pick black or white text per slice, whichever contrasts more with
        # that slice's fill — white-on-yellow/teal was nearly unreadable.
        for color, text in zip(colors, autotexts):
            text.set_color(_text_color_for(color))
        self._ax.legend(
            wedges,
            [f"{label} ({pct:.1f}%)" for label, pct in zip(labels, values)],
            loc="center left",
            bbox_to_anchor=(1.0, 0.5),
            frameon=False,
            fontsize=9,
        )
        self._ax.set_title("Portfolio allocation")
        self._ax.axis("equal")
        self._figure.tight_layout()
        self.draw()
