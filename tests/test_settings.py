from __future__ import annotations

import pytest

from django_bizcal.exceptions import CalendarConfigurationError
from django_bizcal.services import reset_calendar_cache, reset_deadline_policy_cache
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
    assert resolved is get_bizcal_settings()


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


def test_settings_load_deadline_policy_resolver_from_dotted_path(settings) -> None:
    settings.TIME_ZONE = "UTC"
    settings.BIZCAL_DEADLINE_POLICY_RESOLVER = (
        "tests.django_test_project.deadline_policy_resolvers.priority_deadline_policy_resolver"
    )
    reset_calendar_cache()

    resolved = get_bizcal_settings()

    assert resolved.deadline_policy_resolver is not None
    assert callable(resolved.deadline_policy_resolver)


def test_settings_reject_invalid_deadline_policy_resolver(settings) -> None:
    settings.TIME_ZONE = "UTC"
    settings.BIZCAL_DEADLINE_POLICY_RESOLVER = 123
    reset_calendar_cache()

    with pytest.raises(ValueError):
        get_bizcal_settings()


def test_settings_reject_invalid_deadline_policy_mapping_shapes(settings) -> None:
    settings.TIME_ZONE = "UTC"
    settings.BIZCAL_DEADLINE_POLICIES = []
    reset_calendar_cache()

    with pytest.raises(ValueError):
        get_bizcal_settings()

    settings.BIZCAL_DEADLINE_POLICIES = {"support": []}
    reset_calendar_cache()

    with pytest.raises(ValueError):
        get_bizcal_settings()


def test_settings_raise_clear_error_for_unknown_deadline_policy(settings) -> None:
    settings.TIME_ZONE = "UTC"
    settings.BIZCAL_DEADLINE_POLICIES = {
        "support": {"type": "business_duration", "business_hours": 4}
    }
    reset_calendar_cache()

    with pytest.raises(CalendarConfigurationError):
        get_bizcal_settings().get_deadline_policy_config("missing")


def test_global_cache_reset_reloads_settings_objects(settings) -> None:
    settings.TIME_ZONE = "UTC"
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "default"
    reset_calendar_cache()

    before = get_bizcal_settings()
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "support"

    assert get_bizcal_settings() is before

    reset_calendar_cache()
    after = get_bizcal_settings()

    assert after is not before
    assert after.default_calendar_name == "support"


def test_deadline_policy_cache_reset_also_reloads_settings_objects(settings) -> None:
    settings.TIME_ZONE = "UTC"
    settings.BIZCAL_DEADLINE_POLICY_RESOLVER = None
    reset_calendar_cache()

    before = get_bizcal_settings()
    settings.BIZCAL_DEADLINE_POLICY_RESOLVER = (
        "tests.django_test_project.deadline_policy_resolvers.priority_deadline_policy_resolver"
    )

    assert get_bizcal_settings() is before

    reset_deadline_policy_cache()
    after = get_bizcal_settings()

    assert after is not before
    assert after.deadline_policy_resolver is not None
