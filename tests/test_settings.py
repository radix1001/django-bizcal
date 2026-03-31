from __future__ import annotations

import pytest

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
    assert resolved.default_calendar_name == "default"
    assert tuple(resolved.calendar_configs) == ("default",)
    assert resolved.default_calendar_config["weekly_schedule"] == DEFAULT_WEEKLY_SCHEDULE


def test_settings_load_named_calendars(settings) -> None:
    settings.TIME_ZONE = "UTC"
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "support"
    settings.BIZCAL_CALENDARS = {
        "support": {
            "type": "working",
            "tz": "UTC",
            "weekly_schedule": {"0": [["09:00", "18:00"]]},
        },
        "operations": {
            "type": "working",
            "tz": "UTC",
            "weekly_schedule": {"1": [["10:00", "16:00"]]},
        },
    }
    reset_calendar_cache()
    resolved = get_bizcal_settings()
    assert resolved.default_calendar_name == "support"
    assert tuple(resolved.calendar_configs) == ("support", "operations")
    assert resolved.get_calendar_config("operations")["type"] == "working"


def test_settings_reject_conflicting_default_calendar_sources(settings) -> None:
    settings.TIME_ZONE = "UTC"
    settings.BIZCAL_DEFAULT_CALENDAR = {
        "type": "working",
        "tz": "UTC",
        "weekly_schedule": {"0": [["09:00", "18:00"]]},
    }
    settings.BIZCAL_CALENDARS = {
        "default": {
            "type": "working",
            "tz": "UTC",
            "weekly_schedule": {"1": [["09:00", "18:00"]]},
        }
    }
    reset_calendar_cache()
    with pytest.raises(ValueError):
        get_bizcal_settings()


def test_settings_require_default_name_to_exist_in_named_registry(settings) -> None:
    settings.TIME_ZONE = "UTC"
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "support"
    settings.BIZCAL_CALENDARS = {
        "operations": {
            "type": "working",
            "tz": "UTC",
            "weekly_schedule": {"1": [["09:00", "18:00"]]},
        }
    }
    settings.BIZCAL_DEFAULT_CALENDAR = None
    reset_calendar_cache()
    with pytest.raises(ValueError):
        get_bizcal_settings()


def test_settings_load_calendar_resolver_from_dotted_path(settings) -> None:
    settings.TIME_ZONE = "UTC"
    settings.BIZCAL_CALENDAR_RESOLVER = (
        "tests.django_test_project.calendar_resolvers.region_calendar_resolver"
    )
    reset_calendar_cache()

    resolved = get_bizcal_settings()

    assert resolved.calendar_resolver is not None
    assert callable(resolved.calendar_resolver)


def test_settings_reject_invalid_calendar_resolver(settings) -> None:
    settings.TIME_ZONE = "UTC"
    settings.BIZCAL_CALENDAR_RESOLVER = 123
    reset_calendar_cache()

    with pytest.raises(ValueError):
        get_bizcal_settings()
