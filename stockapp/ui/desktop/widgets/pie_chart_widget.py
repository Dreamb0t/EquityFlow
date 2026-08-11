"""
Pie chart for the portfolio's allocation by market value. Same
matplotlib-in-Qt pattern as chart_widget.py, kept as a separate widget since
it has nothing to do with the price timeline.
"""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

# Fixed, visually distinct palette so a given slot's color stays stable across
# refreshes — matplotlib's default cycle only has 10 colors before repeating.
_PALETTE = [
    "#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F",
    "#EDC948", "#B07AA1", "#FF9DA7", "#9C755F", "#BAB0AC",
    "#86BCB6", "#D37295", "#FABFD2", "#B6992D", "#499894",
]


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

        self._ax.pie(
            values,
            labels=[f"{label} ({pct:.1f}%)" for label, pct in zip(labels, values)],
            colors=colors,
            startangle=90,
            wedgeprops={"linewidth": 1, "edgecolor": "white"},
        )
        self._ax.set_title("Portfolio allocation")
        self._ax.axis("equal")
        self.draw()
