from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from django_bizcal.django_api import (
    BusinessDaysPolicy,
    BusinessDurationPolicy,
    DeadlinePolicyResolution,
    build_deadline_policy,
    compute_deadline,
    get_deadline_policy,
    get_deadline_policy_config,
    get_deadline_policy_for,
    get_default_calendar,
    list_configured_deadline_policies,
    reset_deadline_policy_cache,
    resolve_deadline_policy_for,
)
from django_bizcal.exceptions import CalendarConfigurationError, ValidationError
from django_bizcal.services import reset_calendar_cache


def test_django_services_expose_named_deadline_policies(settings) -> None:
    settings.TIME_ZONE = "UTC"
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "support"
    settings.BIZCAL_CALENDARS = {
        "support": {
            "type": "working",
            "tz": "UTC",
            "weekly_schedule": {"0": [["09:00", "18:00"]]},
        }
    }
    settings.BIZCAL_DEADLINE_POLICIES = {
        "support_p1": {"type": "business_duration", "business_hours": 4},
        "support_next": {"type": "next_business_day", "at": "closing"},
    }
    reset_calendar_cache()

    policy = get_deadline_policy("support_p1")
    deadline = compute_deadline(
        "support_p1",
        datetime(2026, 3, 2, 10, 0, tzinfo=ZoneInfo("UTC")),
    )

    assert isinstance(policy, BusinessDurationPolicy)
    assert list_configured_deadline_policies() == ("support_p1", "support_next")
    assert deadline.deadline == datetime(2026, 3, 2, 14, 0, tzinfo=ZoneInfo("UTC"))
    assert deadline.calendar_name == "support"
    assert get_deadline_policy_config("support_p1") == {
        "type": "business_duration",
        "business_hours": 4,
    }
    assert isinstance(
        build_deadline_policy({"type": "business_duration", "business_minutes": 90}),
        BusinessDurationPolicy,
    )


def test_django_services_support_general_business_days_policy(settings) -> None:
    settings.TIME_ZONE = "UTC"
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "support"
    settings.BIZCAL_CALENDARS = {
        "support": {
            "type": "working",
            "tz": "UTC",
            "weekly_schedule": {
                "0": [["09:00", "18:00"]],
                "1": [["09:00", "18:00"]],
                "2": [["09:00", "18:00"]],
                "3": [["09:00", "18:00"]],
                "4": [["09:00", "18:00"]],
            },
        }
    }
    settings.BIZCAL_DEADLINE_POLICIES = {
        "vendor_follow_up": {
            "type": "business_days",
            "business_days": 2,
            "at": "13:30",
            "include_start": True,
        }
    }
    reset_calendar_cache()

    policy = get_deadline_policy("vendor_follow_up")
    deadline = compute_deadline(
        "vendor_follow_up",
        datetime(2026, 3, 5, 10, 0, tzinfo=ZoneInfo("UTC")),
    )

    assert isinstance(policy, BusinessDaysPolicy)
    assert deadline.deadline == datetime(2026, 3, 6, 13, 30, tzinfo=ZoneInfo("UTC"))
    assert get_deadline_policy_config("vendor_follow_up") == {
        "type": "business_days",
        "business_days": 2,
        "at": "13:30",
        "include_start": True,
    }


def test_contextual_deadline_policy_resolution_supports_named_policies(settings) -> None:
    settings.TIME_ZONE = "UTC"
    settings.BIZCAL_DEADLINE_POLICIES = {
        "support_p1": {"type": "business_duration", "business_hours": 4},
        "support_same_day": {"type": "same_business_day", "at": "closing"},
    }
    settings.BIZCAL_DEADLINE_POLICY_RESOLVER = (
        "tests.django_test_project.deadline_policy_resolvers.priority_deadline_policy_resolver"
    )
    reset_calendar_cache()

    resolution = resolve_deadline_policy_for(priority="critical")
    critical = get_deadline_policy_for(priority="critical")
    high = get_deadline_policy_for({"priority": "high"})

    assert resolution == DeadlinePolicyResolution.for_name("support_p1")
    assert critical is get_deadline_policy("support_p1")
    assert high is get_deadline_policy("support_same_day")


def test_contextual_deadline_policy_resolution_supports_config_and_cache(settings) -> None:
    settings.TIME_ZONE = "UTC"
    settings.BIZCAL_DEADLINE_POLICY_RESOLVER = (
        "tests.django_test_project.deadline_policy_resolvers.tenant_deadline_policy_resolver"
    )
    reset_calendar_cache()

    acme_first = get_deadline_policy_for(tenant="acme", priority="high")
    acme_second = get_deadline_policy_for({"tenant": "acme", "priority": "high"})
    globex = get_deadline_policy_for(tenant="globex", priority="high")

    assert acme_first is acme_second
    assert globex is not acme_first

    reset_deadline_policy_cache("tenant_policy:acme:high")

    acme_third = get_deadline_policy_for(tenant="acme", priority="high")

    assert acme_third is not acme_first


def test_compute_deadline_supports_contextual_calendar_resolution(settings) -> None:
    settings.BIZCAL_DEFAULT_TIMEZONE = "UTC"
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "default"
    settings.BIZCAL_CALENDAR_RESOLVER = (
        "tests.django_test_project.calendar_resolvers.tenant_calendar_resolver"
    )
    settings.BIZCAL_DEADLINE_POLICIES = {
        "tenant_cutoff": {
            "type": "cutoff",
            "cutoff": "15:00",
            "before": {"type": "close_of_business"},
            "after": {"type": "next_business_day", "at": "closing"},
        }
    }
    reset_calendar_cache()

    deadline = compute_deadline(
        "tenant_cutoff",
        datetime(2026, 12, 24, 16, 0, tzinfo=ZoneInfo("America/Santiago")),
        tenant="acme",
        region="cl",
    )

    assert deadline.calendar_name == "tenant:acme"
    assert deadline.deadline == datetime(
        2026,
        12,
        31,
        18,
        0,
        tzinfo=ZoneInfo("America/Santiago"),
    )


def test_compute_deadline_can_resolve_policy_and_calendar_from_shared_context(settings) -> None:
    settings.BIZCAL_DEFAULT_TIMEZONE = "UTC"
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "default"
    settings.BIZCAL_CALENDAR_RESOLVER = (
        "tests.django_test_project.calendar_resolvers.tenant_calendar_resolver"
    )
    settings.BIZCAL_DEADLINE_POLICY_RESOLVER = (
        "tests.django_test_project.deadline_policy_resolvers.tenant_deadline_policy_resolver"
    )
    reset_calendar_cache()

    deadline = compute_deadline(
        policy_name=None,
        start=datetime(2026, 12, 24, 9, 0, tzinfo=ZoneInfo("America/Santiago")),
        tenant="acme",
        region="cl",
        priority="critical",
    )

    assert deadline.calendar_name == "tenant:acme"
    assert deadline.deadline == datetime(
        2026,
        12,
        24,
        13,
        0,
        tzinfo=ZoneInfo("America/Santiago"),
    )


def test_compute_deadline_rejects_mixed_explicit_and_contextual_calendar_inputs(
    settings,
) -> None:
    settings.TIME_ZONE = "UTC"
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "support"
    settings.BIZCAL_CALENDARS = {
        "support": {
            "type": "working",
            "tz": "UTC",
            "weekly_schedule": {"0": [["09:00", "18:00"]]},
        }
    }
    settings.BIZCAL_DEADLINE_POLICIES = {
        "support_p1": {"type": "business_duration", "business_hours": 4},
    }
    reset_calendar_cache()

    with pytest.raises(ValidationError):
        compute_deadline(
            "support_p1",
            datetime(2026, 3, 2, 10, 0, tzinfo=ZoneInfo("UTC")),
            calendar=get_default_calendar(),
            tenant="acme",
        )


def test_contextual_deadline_policy_resolution_validates_configuration(settings) -> None:
    settings.TIME_ZONE = "UTC"
    settings.BIZCAL_DEFAULT_CALENDAR_NAME = "default"
    reset_calendar_cache()

    with pytest.raises(CalendarConfigurationError):
        get_deadline_policy_for(priority="critical")

    settings.BIZCAL_DEADLINE_POLICY_RESOLVER = (
        "tests.django_test_project.deadline_policy_resolvers.invalid_deadline_policy_resolver"
    )
    reset_calendar_cache()

    with pytest.raises(CalendarConfigurationError):
        get_deadline_policy_for(priority="critical")

    with pytest.raises(ValidationError):
        compute_deadline(
            policy_name=None,
            start=datetime(2026, 3, 2, 10, 0, tzinfo=ZoneInfo("UTC")),
        )
