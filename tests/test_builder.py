from __future__ import annotations

import pytest

from django_bizcal import CalendarBuilder, UnionCalendar, WorkingCalendar
from django_bizcal.exceptions import CalendarConfigurationError


def test_builder_creates_working_calendar_from_dict() -> None:
    calendar = CalendarBuilder.from_dict(
        {
            "type": "working",
            "tz": "UTC",
            "weekly_schedule": {
                "0": [["09:00", "13:00"], ["14:00", "18:00"]],
            },
            "day_overrides": {
                "2026-03-02": [["10:00", "12:00"]],
            },
        }
    )
    assert isinstance(calendar, WorkingCalendar)
    assert len(calendar.business_windows_for_day("2026-03-02")) == 1


def test_builder_creates_nested_union_calendar() -> None:
    calendar = CalendarBuilder.from_dict(
        {
            "type": "union",
            "tz": "UTC",
            "children": [
                {
                    "type": "working",
                    "tz": "UTC",
                    "weekly_schedule": {"0": [["09:00", "11:00"]]},
                },
                {
                    "type": "working",
                    "tz": "UTC",
                    "weekly_schedule": {"0": [["13:00", "15:00"]]},
                },
            ],
        }
    )
    assert isinstance(calendar, UnionCalendar)
    assert len(calendar.business_windows_for_day("2026-03-02")) == 2


def test_builder_requires_known_type() -> None:
    with pytest.raises(CalendarConfigurationError):
        CalendarBuilder.from_dict({"type": "mystery"})


def test_builder_requires_years_for_country_holidays() -> None:
    with pytest.raises(CalendarConfigurationError):
        CalendarBuilder.from_dict(
            {
                "type": "working",
                "country": "CL",
                "tz": "UTC",
                "weekly_schedule": {"0": [["09:00", "18:00"]]},
            }
        )

