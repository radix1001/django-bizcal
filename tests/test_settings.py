from __future__ import annotations

from django_bizcal.services import reset_calendar_cache
from django_bizcal.settings import DEFAULT_WEEKLY_SCHEDULE, get_bizcal_settings


def test_settings_load_defaults(settings) -> None:
    settings.TIME_ZONE = "UTC"
    settings.BIZCAL_DEFAULT_COUNTRY = "CL"
    settings.BIZCAL_PRELOAD_YEARS = [2026, 2027]
    reset_calendar_cache()
    resolved = get_bizcal_settings()
    assert resolved.default_timezone.key == "UTC"
    assert resolved.default_country == "CL"
    assert resolved.preload_years == (2026, 2027)
    assert resolved.default_calendar_config["weekly_schedule"] == DEFAULT_WEEKLY_SCHEDULE

