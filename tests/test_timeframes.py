from stockapp.analysis.timeframes import is_intraday, moving_average_window


def test_one_day_is_intraday():
    assert is_intraday(1) is True


def test_multi_day_is_not_intraday():
    assert is_intraday(5) is False
    assert is_intraday(365) is False


def test_moving_average_window_capped_by_data_length():
    assert moving_average_window(5, target=20) == 5


def test_moving_average_window_uses_target_when_enough_data():
    assert moving_average_window(100, target=20) == 20


def test_moving_average_window_handles_empty():
    assert moving_average_window(0) == 1
