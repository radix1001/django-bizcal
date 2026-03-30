from __future__ import annotations

from datetime import date

from django_bizcal.providers import CompositeHolidayProvider, HolidaysProvider, SetHolidayProvider


def test_set_holiday_provider_matches_custom_days() -> None:
    provider = SetHolidayProvider.from_dates(["2026-12-24", date(2026, 12, 31)])
    assert provider.is_holiday(date(2026, 12, 24)) is True
    assert provider.is_holiday(date(2026, 12, 25)) is False


def test_composite_holiday_provider_combines_official_and_custom_days() -> None:
    official = HolidaysProvider.from_country(country="CL", years=[2026])
    custom = SetHolidayProvider.from_dates(["2026-12-24"])
    provider = CompositeHolidayProvider.combine([official, custom])
    assert provider is not None
    assert provider.is_holiday(date(2026, 1, 1)) is True
    assert provider.is_holiday(date(2026, 12, 24)) is True

