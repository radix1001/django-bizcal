from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from django.apps import apps

from django_bizcal import WorkingCalendar, deadline_for
from django_bizcal.exceptions import CalendarConfigurationError
from django_bizcal.services import (
    build_calendar,
    get_calendar,
    get_default_calendar,
    list_configured_calendars,
    now,
    reset_calendar_cache,
)


def test_app_config_is_registered() -> None:
    config = apps.get_app_config("django_bizcal")
    assert config.name == "django_bizcal"
    assert config.verbose_name == "Django Business Calendar"


def test_default_calendar_service_uses_settings(settings) -> None:
    settings.BIZCAL_DEFAULT_TIMEZONE = "UTC"
    settings.BIZCAL_DEFAULT_COUNTRY = "CL"
    settings.BIZCAL_PRELOAD_YEARS = [2026]
    settings.BIZCAL_DEFAULT_CALENDAR = {
        "type": "working",
        "tz": "UTC",
        "weekly_schedule": {"0": [["09:00", "18:00"]]},
    }
    reset_calendar_cache()
    calendar = get_default_calendar()
    assert isinstance(calendar, WorkingCalendar)
    assert calendar.tz.key == "UTC"


def test_named_calendar_registry_service_uses_settings(settings) -> None:
    settings.BIZCAL_DEFAULT_TIMEZONE = "UTC"
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

    support = get_calendar("support")
    operations = get_calendar("operations")

    assert isinstance(support, WorkingCalendar)
    assert isinstance(operations, WorkingCalendar)
    assert support is get_calendar("support")
    assert support.calendar_name == "support"
    assert deadline_for(
        datetime(2026, 3, 2, 10, 0, tzinfo=ZoneInfo("UTC")),
        timedelta(hours=2),
        calendar=support,
    ).calendar_name == "support"
    assert support.deadline_for(
        datetime(2026, 3, 2, 10, 0, tzinfo=ZoneInfo("UTC")),
        timedelta(hours=2),
    ).calendar_name == "support"
    assert list_configured_calendars() == ("support", "operations")


def test_build_calendar_uses_django_defaults(settings) -> None:
    settings.BIZCAL_DEFAULT_TIMEZONE = "UTC"
    settings.BIZCAL_DEFAULT_COUNTRY = "CL"
    settings.BIZCAL_PRELOAD_YEARS = [2026]
    reset_calendar_cache()
    calendar = build_calendar(
        {
            "type": "working",
            "weekly_schedule": {"0": [["09:00", "18:00"]]},
        }
    )
    assert isinstance(calendar, WorkingCalendar)
    assert calendar.tz.key == "UTC"


def test_now_returns_aware_datetime() -> None:
    current = now()
    assert current.tzinfo is not None
    assert current.utcoffset() is not None


def test_default_calendar_can_be_used_for_arithmetic(settings) -> None:
    settings.BIZCAL_DEFAULT_TIMEZONE = "UTC"
    settings.BIZCAL_DEFAULT_CALENDAR = {
        "type": "working",
        "tz": "UTC",
        "weekly_schedule": {"0": [["09:00", "18:00"]]},
    }
    reset_calendar_cache()
    calendar = get_default_calendar()
    start = datetime(2026, 3, 2, 10, 0, tzinfo=ZoneInfo("UTC"))
    assert calendar.add_business_hours(start, 2) == datetime(
        2026,
        3,
        2,
        12,
        0,
        tzinfo=ZoneInfo("UTC"),
    )


def test_named_calendar_lookup_raises_for_unknown_names(settings) -> None:
    settings.BIZCAL_DEFAULT_TIMEZONE = "UTC"
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "support"
    settings.BIZCAL_CALENDARS = {
        "support": {
            "type": "working",
            "tz": "UTC",
            "weekly_schedule": {"0": [["09:00", "18:00"]]},
        }
    }
    reset_calendar_cache()
    with pytest.raises(CalendarConfigurationError):
        get_calendar("missing")
