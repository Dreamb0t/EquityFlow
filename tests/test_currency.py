"""CurrencyService tests using a stub FxRateProvider — no network involved."""

from stockapp.core.interfaces import FxRateProvider
from stockapp.services.currency_service import CurrencyService


class StubFxRateProvider(FxRateProvider):
    def __init__(self, rates: dict[tuple[str, str], float]):
        self.rates = rates
        self.calls = 0

    def get_rate(self, base: str, quote: str) -> float:
        self.calls += 1
        return self.rates[(base, quote)]


def test_same_currency_is_always_rate_one():
    service = CurrencyService(StubFxRateProvider({}))
    assert service.get_rate("USD", "USD") == 1.0


def test_convert_applies_rate():
    provider = StubFxRateProvider({("USD", "DKK"): 6.9})
    service = CurrencyService(provider)
    assert service.convert(100, "USD", "DKK") == 690.0


def test_rate_is_cached_between_calls():
    provider = StubFxRateProvider({("USD", "DKK"): 6.9})
    service = CurrencyService(provider)
    service.get_rate("USD", "DKK")
    service.get_rate("USD", "DKK")
    assert provider.calls == 1


def test_clear_cache_forces_refetch():
    provider = StubFxRateProvider({("USD", "DKK"): 6.9})
    service = CurrencyService(provider)
    service.get_rate("USD", "DKK")
    service.clear_cache()
    service.get_rate("USD", "DKK")
    assert provider.calls == 2
