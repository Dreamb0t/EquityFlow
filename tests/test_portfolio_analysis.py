from stockapp.analysis.portfolio_analysis import compute_distribution


def test_distribution_sums_to_100():
    result = compute_distribution({"AAPL": 300.0, "MSFT": 700.0})
    assert result["AAPL"] == 30.0
    assert result["MSFT"] == 70.0
    assert sum(result.values()) == 100.0


def test_distribution_ignores_non_positive_values():
    result = compute_distribution({"AAPL": 100.0, "MSFT": 0.0, "TSLA": -50.0})
    assert "MSFT" not in result
    assert "TSLA" not in result
    assert result["AAPL"] == 100.0


def test_empty_input_returns_empty():
    assert compute_distribution({}) == {}


def test_all_zero_returns_empty():
    assert compute_distribution({"AAPL": 0.0}) == {}


def test_currency_target_invariance():
    """Percentages shouldn't depend on which currency values were converted
    into, as long as the SAME rate is applied to every entry (this is the
    property the portfolio pie chart relies on to skip re-fetching on a
    currency change)."""
    native = {"AAPL": 300.0, "MSFT": 700.0}
    rate = 6.9  # e.g. USD -> DKK
    converted = {k: v * rate for k, v in native.items()}
    assert compute_distribution(native) == compute_distribution(converted)
