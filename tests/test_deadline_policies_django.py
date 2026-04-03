from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from django_bizcal.django_api import (
    BusinessDurationPolicy,
    build_deadline_policy,
    compute_deadline,
    get_deadline_policy,
    get_deadline_policy_config,
    get_default_calendar,
    list_configured_deadline_policies,
)
from django_bizcal.exceptions import ValidationError
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
