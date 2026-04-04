from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from django_bizcal import (
    BusinessDaysAtClosePolicy,
    BusinessDaysPolicy,
    BusinessDurationPolicy,
    CloseOfBusinessPolicy,
    CutoffPolicy,
    DeadlinePolicyBuilder,
    NextBusinessDayPolicy,
    SameBusinessDayPolicy,
    WorkingCalendar,
)
from django_bizcal.exceptions import ValidationError


def test_business_duration_policy_resolves_like_deadline_helper(
    support_calendar: WorkingCalendar,
) -> None:
    start = datetime(2026, 3, 2, 10, 0, tzinfo=ZoneInfo("America/Santiago"))

    deadline = BusinessDurationPolicy(timedelta(hours=4)).resolve(
        start,
        calendar=support_calendar,
        calendar_name="support",
    )

    assert deadline.deadline == datetime(2026, 3, 2, 15, 0, tzinfo=ZoneInfo("America/Santiago"))
    assert deadline.calendar_name == "support"
    assert deadline.service_time == timedelta(hours=4)


def test_close_of_business_policy_rolls_forward_when_needed(
    support_calendar: WorkingCalendar,
) -> None:
    before_close = CloseOfBusinessPolicy().resolve(
        datetime(2026, 3, 2, 10, 0, tzinfo=ZoneInfo("America/Santiago")),
        calendar=support_calendar,
    )
    after_close = CloseOfBusinessPolicy().resolve(
        datetime(2026, 3, 2, 19, 0, tzinfo=ZoneInfo("America/Santiago")),
        calendar=support_calendar,
    )

    assert before_close.deadline == datetime(
        2026,
        3,
        2,
        18,
        0,
        tzinfo=ZoneInfo("America/Santiago"),
    )
    assert after_close.deadline == datetime(
        2026,
        3,
        3,
        18,
        0,
        tzinfo=ZoneInfo("America/Santiago"),
    )


def test_next_business_day_and_business_days_at_close_policies(
    support_calendar: WorkingCalendar,
) -> None:
    next_day = NextBusinessDayPolicy(at="13:30").resolve(
        datetime(2026, 3, 6, 17, 30, tzinfo=ZoneInfo("America/Santiago")),
        calendar=support_calendar,
    )
    include_start = BusinessDaysAtClosePolicy(business_days=1, include_start=True).resolve(
        datetime(2026, 3, 5, 10, 0, tzinfo=ZoneInfo("America/Santiago")),
        calendar=support_calendar,
    )
    late_start = BusinessDaysAtClosePolicy(business_days=1, include_start=True).resolve(
        datetime(2026, 3, 5, 20, 0, tzinfo=ZoneInfo("America/Santiago")),
        calendar=support_calendar,
    )

    assert next_day.deadline == datetime(
        2026,
        3,
        9,
        14,
        0,
        tzinfo=ZoneInfo("America/Santiago"),
    )
    assert include_start.deadline == datetime(
        2026,
        3,
        5,
        18,
        0,
        tzinfo=ZoneInfo("America/Santiago"),
    )
    assert late_start.deadline == datetime(
        2026,
        3,
        6,
        17,
        0,
        tzinfo=ZoneInfo("America/Santiago"),
    )


def test_business_days_policy_supports_fixed_time_boundaries(
    support_calendar: WorkingCalendar,
) -> None:
    same_day_counts = BusinessDaysPolicy(business_days=2, at="13:30", include_start=True).resolve(
        datetime(2026, 3, 5, 10, 0, tzinfo=ZoneInfo("America/Santiago")),
        calendar=support_calendar,
    )
    passed_boundary_rolls = BusinessDaysPolicy(
        business_days=2,
        at="13:30",
        include_start=True,
    ).resolve(
        datetime(2026, 3, 5, 16, 0, tzinfo=ZoneInfo("America/Santiago")),
        calendar=support_calendar,
    )
    next_opening = BusinessDaysPolicy(business_days=1, at="opening").resolve(
        datetime(2026, 3, 5, 16, 0, tzinfo=ZoneInfo("America/Santiago")),
        calendar=support_calendar,
    )

    assert same_day_counts.deadline == datetime(
        2026,
        3,
        6,
        14,
        0,
        tzinfo=ZoneInfo("America/Santiago"),
    )
    assert passed_boundary_rolls.deadline == datetime(
        2026,
        3,
        9,
        14,
        0,
        tzinfo=ZoneInfo("America/Santiago"),
    )
    assert next_opening.deadline == datetime(
        2026,
        3,
        6,
        9,
        0,
        tzinfo=ZoneInfo("America/Santiago"),
    )


def test_same_business_day_policy_resolves_same_day_or_rolls_forward(
    support_calendar: WorkingCalendar,
) -> None:
    same_day = SameBusinessDayPolicy(at="15:30").resolve(
        datetime(2026, 3, 5, 10, 0, tzinfo=ZoneInfo("America/Santiago")),
        calendar=support_calendar,
    )
    rolled = SameBusinessDayPolicy(at="15:30").resolve(
        datetime(2026, 3, 5, 16, 0, tzinfo=ZoneInfo("America/Santiago")),
        calendar=support_calendar,
    )

    assert same_day.deadline == datetime(
        2026,
        3,
        5,
        15,
        30,
        tzinfo=ZoneInfo("America/Santiago"),
    )
    assert rolled.deadline == datetime(
        2026,
        3,
        6,
        15,
        30,
        tzinfo=ZoneInfo("America/Santiago"),
    )


def test_cutoff_policy_dispatches_between_nested_policies(
    support_calendar: WorkingCalendar,
) -> None:
    policy = CutoffPolicy(
        cutoff="15:00",
        before=CloseOfBusinessPolicy(),
        after=NextBusinessDayPolicy(at="closing"),
    )

    before_cutoff = policy.resolve(
        datetime(2026, 3, 5, 14, 30, tzinfo=ZoneInfo("America/Santiago")),
        calendar=support_calendar,
    )
    after_cutoff = policy.resolve(
        datetime(2026, 3, 5, 15, 30, tzinfo=ZoneInfo("America/Santiago")),
        calendar=support_calendar,
    )

    assert before_cutoff.deadline == datetime(
        2026,
        3,
        5,
        18,
        0,
        tzinfo=ZoneInfo("America/Santiago"),
    )
    assert after_cutoff.deadline == datetime(
        2026,
        3,
        6,
        17,
        0,
        tzinfo=ZoneInfo("America/Santiago"),
    )


def test_deadline_policy_builder_supports_supported_policy_types(
    support_calendar: WorkingCalendar,
) -> None:
    cutoff_config = {
        "type": "cutoff",
        "cutoff": "15:00",
        "before": {"type": "close_of_business"},
        "after": {
            "type": "business_duration",
            "business_hours": 8,
        },
    }
    business_days_config = {
        "type": "business_days",
        "business_days": 2,
        "at": "13:30",
        "include_start": True,
    }
    policy = DeadlinePolicyBuilder.from_dict(cutoff_config)
    business_days_policy = DeadlinePolicyBuilder.from_dict(business_days_config)

    deadline = policy.resolve(
        datetime(2026, 3, 5, 16, 0, tzinfo=ZoneInfo("America/Santiago")),
        calendar=support_calendar,
    )
    business_days_deadline = business_days_policy.resolve(
        datetime(2026, 3, 5, 10, 0, tzinfo=ZoneInfo("America/Santiago")),
        calendar=support_calendar,
    )

    assert deadline.deadline == datetime(
        2026,
        3,
        6,
        16,
        0,
        tzinfo=ZoneInfo("America/Santiago"),
    )
    assert business_days_deadline.deadline == datetime(
        2026,
        3,
        6,
        14,
        0,
        tzinfo=ZoneInfo("America/Santiago"),
    )
    assert DeadlinePolicyBuilder.to_dict(policy) == cutoff_config
    assert DeadlinePolicyBuilder.to_dict(business_days_policy) == business_days_config
    assert DeadlinePolicyBuilder.to_dict(SameBusinessDayPolicy(at="15:30")) == {
        "type": "same_business_day",
        "at": "15:30",
    }


def test_deadline_policy_builder_serializes_normalized_time_values() -> None:
    policy = NextBusinessDayPolicy(at="13:30:15")

    assert DeadlinePolicyBuilder.to_dict(policy) == {
        "type": "next_business_day",
        "at": "13:30:15",
    }


def test_calendar_policy_methods_resolve_objects_and_dicts(
    support_calendar: WorkingCalendar,
) -> None:
    start = datetime(2026, 3, 2, 10, 0, tzinfo=ZoneInfo("America/Santiago"))

    object_deadline = support_calendar.resolve_deadline_policy(
        start,
        BusinessDurationPolicy(timedelta(hours=4)),
        calendar_name="support",
    )
    dict_deadline = support_calendar.resolve_deadline_policy_dict(
        start,
        {"type": "business_duration", "business_hours": 4},
        calendar_name="support",
    )

    assert object_deadline.deadline == dict_deadline.deadline
    assert object_deadline.calendar_name == "support"


def test_deadline_policy_builder_validates_invalid_configs() -> None:
    with pytest.raises(ValidationError):
        DeadlinePolicyBuilder.from_dict([])
    with pytest.raises(ValidationError):
        DeadlinePolicyBuilder.from_dict({})
    with pytest.raises(ValidationError):
        DeadlinePolicyBuilder.from_dict({"type": "business_duration"})
    with pytest.raises(ValidationError):
        DeadlinePolicyBuilder.from_dict(
            {
                "type": "business_duration",
                "business_hours": -1,
                "business_minutes": 120,
            }
        )
    with pytest.raises(ValidationError):
        DeadlinePolicyBuilder.from_dict({"type": "business_days"})
    with pytest.raises(ValidationError):
        DeadlinePolicyBuilder.from_dict({"type": "business_days_at_close"})
    with pytest.raises(ValidationError):
        DeadlinePolicyBuilder.from_dict({"type": "cutoff", "cutoff": "15:00"})
    with pytest.raises(ValidationError):
        DeadlinePolicyBuilder.from_dict(
            {
                "type": "cutoff",
                "cutoff": "15:00",
                "before": "close_of_business",
                "after": {"type": "next_business_day"},
            }
        )
    with pytest.raises(ValidationError):
        BusinessDaysPolicy(business_days=0)
    with pytest.raises(ValidationError):
        BusinessDaysAtClosePolicy(business_days=0)
