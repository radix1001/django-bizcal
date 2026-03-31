from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from django_bizcal import WorkingCalendar
from django_bizcal.django_api import CalendarResolution
from django_bizcal.exceptions import CalendarConfigurationError, ValidationError
from django_bizcal.services import (
    get_calendar,
    get_calendar_for,
    reset_calendar_cache,
    resolve_calendar_for,
    set_calendar_day_override,
    set_calendar_holiday,
)


def test_get_calendar_for_uses_string_resolver_for_named_calendars(settings) -> None:
    settings.BIZCAL_DEFAULT_TIMEZONE = "UTC"
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "support_cl"
    settings.BIZCAL_CALENDARS = {
        "support_cl": {
            "type": "working",
            "tz": "UTC",
            "weekly_schedule": {"3": [["09:00", "18:00"]]},
        },
        "support_mx": {
            "type": "working",
            "tz": "UTC",
            "weekly_schedule": {"3": [["10:00", "16:00"]]},
        },
    }
    settings.BIZCAL_CALENDAR_RESOLVER = (
        "tests.django_test_project.calendar_resolvers.region_calendar_resolver"
    )
    reset_calendar_cache()

    cl = get_calendar_for(region="cl")
    mx = get_calendar_for({"region": "mx"})

    assert cl is get_calendar("support_cl")
    assert mx is get_calendar("support_mx")
    assert isinstance(cl, WorkingCalendar)


def test_resolve_calendar_for_returns_normalized_resolution(settings) -> None:
    settings.BIZCAL_DEFAULT_TIMEZONE = "UTC"
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "support_cl"
    settings.BIZCAL_CALENDARS = {
        "support_cl": {
            "type": "working",
            "tz": "UTC",
            "weekly_schedule": {"3": [["09:00", "18:00"]]},
        }
    }
    settings.BIZCAL_CALENDAR_RESOLVER = (
        "tests.django_test_project.calendar_resolvers.region_calendar_resolver"
    )

    resolution = resolve_calendar_for(region="cl")

    assert resolution == CalendarResolution.for_name("support_cl")


def test_get_calendar_for_supports_contextual_config_resolution_and_cache(settings) -> None:
    settings.BIZCAL_DEFAULT_TIMEZONE = "UTC"
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "default"
    settings.BIZCAL_CALENDAR_RESOLVER = (
        "tests.django_test_project.calendar_resolvers.tenant_calendar_resolver"
    )
    reset_calendar_cache()

    acme_first = get_calendar_for(tenant="acme", region="cl")
    acme_second = get_calendar_for({"tenant": "acme", "region": "cl"})
    globex = get_calendar_for(tenant="globex", region="cl")

    assert acme_first is acme_second
    assert globex is not acme_first
    assert acme_first.business_windows_for_day(date(2026, 12, 24))[0].start == datetime(
        2026,
        12,
        24,
        9,
        0,
        tzinfo=ZoneInfo("America/Santiago"),
    )


@pytest.mark.django_db
def test_contextual_resolution_applies_db_overrides_and_named_invalidation(settings) -> None:
    settings.BIZCAL_ENABLE_DB_MODELS = True
    settings.BIZCAL_DEFAULT_TIMEZONE = "UTC"
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "default"
    settings.BIZCAL_CALENDAR_RESOLVER = (
        "tests.django_test_project.calendar_resolvers.tenant_calendar_resolver"
    )
    reset_calendar_cache()

    before = get_calendar_for(tenant="acme", region="cl")
    assert before.is_business_day(date(2026, 12, 24)) is True

    set_calendar_holiday("tenant:acme", "2026-12-24", name="Tenant shutdown")

    after_holiday = get_calendar_for(tenant="acme", region="cl")
    assert after_holiday is not before
    assert after_holiday.is_business_day(date(2026, 12, 24)) is False

    set_calendar_day_override("tenant:acme", "2026-12-24", [("10:00", "12:00")])

    after_override = get_calendar_for(tenant="acme", region="cl")
    windows = after_override.business_windows_for_day(date(2026, 12, 24))

    assert after_override is not after_holiday
    assert len(windows) == 1
    assert windows[0].start == datetime(
        2026,
        12,
        24,
        10,
        0,
        tzinfo=ZoneInfo("America/Santiago"),
    )


def test_get_calendar_for_requires_configured_resolver(settings) -> None:
    settings.BIZCAL_DEFAULT_TIMEZONE = "UTC"
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "default"
    reset_calendar_cache()

    with pytest.raises(CalendarConfigurationError):
        get_calendar_for(tenant="acme")


def test_invalid_resolver_output_raises(settings) -> None:
    settings.BIZCAL_DEFAULT_TIMEZONE = "UTC"
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "default"
    settings.BIZCAL_CALENDAR_RESOLVER = (
        "tests.django_test_project.calendar_resolvers.invalid_calendar_resolver"
    )
    reset_calendar_cache()

    with pytest.raises(CalendarConfigurationError):
        get_calendar_for(tenant="acme")


def test_settings_accept_direct_callable_resolver(settings) -> None:
    from tests.django_test_project.calendar_resolvers import region_calendar_resolver

    settings.BIZCAL_DEFAULT_TIMEZONE = "UTC"
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "support_cl"
    settings.BIZCAL_CALENDARS = {
        "support_cl": {
            "type": "working",
            "tz": "UTC",
            "weekly_schedule": {"3": [["09:00", "18:00"]]},
        }
    }
    settings.BIZCAL_CALENDAR_RESOLVER = region_calendar_resolver
    reset_calendar_cache()

    resolved = get_calendar_for(region="cl")

    assert resolved is get_calendar("support_cl")


def test_get_calendar_for_rejects_duplicate_context_keys(settings) -> None:
    settings.BIZCAL_DEFAULT_TIMEZONE = "UTC"
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "support_cl"
    settings.BIZCAL_CALENDARS = {
        "support_cl": {
            "type": "working",
            "tz": "UTC",
            "weekly_schedule": {"3": [["09:00", "18:00"]]},
        }
    }
    settings.BIZCAL_CALENDAR_RESOLVER = (
        "tests.django_test_project.calendar_resolvers.region_calendar_resolver"
    )

    with pytest.raises(ValidationError):
        get_calendar_for({"region": "cl"}, region="mx")
