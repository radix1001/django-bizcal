from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from django_bizcal import (
    CalendarBuilder,
    DifferenceCalendar,
    OverrideCalendar,
    UnionCalendar,
    WorkingCalendar,
)
from django_bizcal.calendars.base import BusinessCalendar
from django_bizcal.exceptions import CalendarConfigurationError
from django_bizcal.intervals import BusinessInterval
from django_bizcal.providers import (
    CompositeHolidayProvider,
    HolidaysProvider,
    SetHolidayProvider,
)


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


def test_builder_to_dict_roundtrips_working_calendar() -> None:
    source = {
        "type": "working",
        "tz": "America/Santiago",
        "country": "CL",
        "years": [2026],
        "weekly_schedule": {
            "0": [["09:00", "13:00"], ["14:00", "18:00"]],
            "4": [["09:00", "17:00"]],
        },
        "extra_holidays": ["2026-12-24"],
        "day_overrides": {"2026-12-31": None},
        "name": "support-cl",
    }
    calendar = CalendarBuilder.from_dict(source)

    serialized = CalendarBuilder.to_dict(calendar)

    assert serialized == {
        "type": "working",
        "tz": "America/Santiago",
        "country": "CL",
        "years": [2026],
        "weekly_schedule": {
            "0": [("09:00", "13:00"), ("14:00", "18:00")],
            "4": [("09:00", "17:00")],
        },
        "extra_holidays": ["2026-12-24"],
        "day_overrides": {"2026-12-31": None},
        "name": "support-cl",
    }
    restored = CalendarBuilder.from_dict(serialized)
    assert restored.business_windows_for_day("2026-03-02") == calendar.business_windows_for_day(
        "2026-03-02"
    )
    assert restored.business_windows_for_day("2026-12-31") == ()


def test_builder_to_dict_roundtrips_composite_calendars() -> None:
    union = CalendarBuilder.from_dict(
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
    override = OverrideCalendar(union, {"2026-03-02": [("10:00", "12:00")]}, tz="UTC")
    difference = DifferenceCalendar(
        override,
        WorkingCalendar(tz="UTC", weekly_schedule={0: [("11:00", "11:30")]}),
        tz="UTC",
    )

    serialized = CalendarBuilder.to_dict(difference)
    restored = CalendarBuilder.from_dict(serialized)

    assert serialized == {
        "type": "difference",
        "tz": "UTC",
        "base": {
            "type": "override",
            "tz": "UTC",
            "base": {
                "type": "union",
                "tz": "UTC",
                "children": [
                    {
                        "type": "working",
                        "tz": "UTC",
                        "weekly_schedule": {"0": [("09:00", "11:00")]},
                    },
                    {
                        "type": "working",
                        "tz": "UTC",
                        "weekly_schedule": {"0": [("13:00", "15:00")]},
                    },
                ],
            },
            "overrides": {"2026-03-02": [("10:00", "12:00")]},
        },
        "subtract": {
            "type": "working",
            "tz": "UTC",
            "weekly_schedule": {"0": [("11:00", "11:30")]},
        },
    }
    assert restored.business_windows_for_day("2026-03-02") == difference.business_windows_for_day(
        "2026-03-02"
    )


def test_builder_handles_intersection_and_difference_children_serialization() -> None:
    calendar = CalendarBuilder.from_dict(
        {
            "type": "intersection",
            "tz": "UTC",
            "children": [
                {
                    "type": "working",
                    "tz": "UTC",
                    "weekly_schedule": {"0": [["09:00", "12:00"]]},
                },
                {
                    "type": "working",
                    "tz": "UTC",
                    "weekly_schedule": {"0": [["10:00", "15:00"]]},
                },
            ],
        }
    )
    serialized = CalendarBuilder.to_dict(calendar)
    difference = CalendarBuilder.from_dict(
        {
            "type": "difference",
            "tz": "UTC",
            "children": [
                serialized,
                {
                    "type": "working",
                    "tz": "UTC",
                    "weekly_schedule": {"0": [["10:30", "11:00"]]},
                },
            ],
        }
    )

    assert serialized["type"] == "intersection"
    assert difference.business_windows_for_day("2026-03-02") == (
        BusinessInterval(
            datetime(2026, 3, 2, 10, 0, tzinfo=ZoneInfo("UTC")),
            datetime(2026, 3, 2, 10, 30, tzinfo=ZoneInfo("UTC")),
        ),
        BusinessInterval(
            datetime(2026, 3, 2, 11, 0, tzinfo=ZoneInfo("UTC")),
            datetime(2026, 3, 2, 12, 0, tzinfo=ZoneInfo("UTC")),
        ),
    )


def test_builder_serializes_supported_holiday_provider_shapes() -> None:
    official_only = WorkingCalendar(
        tz="UTC",
        weekly_schedule={0: [("09:00", "18:00")]},
        holiday_provider=HolidaysProvider.from_country(
            "CL",
            years=[2026],
            subdivision="RM",
            observed=False,
        ),
    )
    extra_only = WorkingCalendar(
        tz="UTC",
        weekly_schedule={0: [("09:00", "18:00")]},
        holiday_provider=SetHolidayProvider.from_dates(["2026-03-02"]),
    )
    mixed = WorkingCalendar(
        tz="UTC",
        weekly_schedule={0: [("09:00", "18:00")]},
        holiday_provider=CompositeHolidayProvider.combine(
            [
                HolidaysProvider.from_country("CL", years=[2026]),
                SetHolidayProvider.from_dates(["2026-03-02"]),
            ]
        ),
    )

    official_config = CalendarBuilder.to_dict(official_only)

    assert official_config["observed"] is False
    assert official_config["subdivision"] == "RM"
    assert CalendarBuilder.to_dict(extra_only)["extra_holidays"] == ["2026-03-02"]
    assert CalendarBuilder.to_dict(mixed)["country"] == "CL"


def test_builder_to_dict_rejects_unsupported_shapes() -> None:
    class AdHocCalendar(BusinessCalendar):
        def _business_windows_for_day_local(self, day: date) -> tuple[BusinessInterval, ...]:
            return ()

    class AdHocHolidayProvider:
        def is_holiday(self, day: date) -> bool:
            return False

    with pytest.raises(CalendarConfigurationError):
        CalendarBuilder.to_dict(AdHocCalendar("UTC"))

    multiple_official = WorkingCalendar(
        tz="UTC",
        weekly_schedule={0: [("09:00", "18:00")]},
        holiday_provider=CompositeHolidayProvider(
            (
                HolidaysProvider.from_country("CL", years=[2026]),
                HolidaysProvider.from_country("MX", years=[2026]),
            )
        ),
    )
    unsupported_provider = WorkingCalendar(
        tz="UTC",
        weekly_schedule={0: [("09:00", "18:00")]},
        holiday_provider=CompositeHolidayProvider((AdHocHolidayProvider(),)),
    )

    with pytest.raises(CalendarConfigurationError):
        CalendarBuilder.to_dict(multiple_official)
    with pytest.raises(CalendarConfigurationError):
        CalendarBuilder.to_dict(unsupported_provider)

    direct_unsupported_provider = WorkingCalendar(
        tz="UTC",
        weekly_schedule={0: [("09:00", "18:00")]},
        holiday_provider=AdHocHolidayProvider(),  # type: ignore[arg-type]
    )

    with pytest.raises(CalendarConfigurationError):
        CalendarBuilder.to_dict(direct_unsupported_provider)


def test_builder_to_dict_serializes_time_values_with_seconds() -> None:
    calendar = WorkingCalendar(
        tz="UTC",
        weekly_schedule={0: [(time(9, 0, 15), time(18, 0, 45))]},
        day_overrides={date(2026, 3, 2): [(time(10, 30, 5), time(12, 45, 10))]},
    )

    serialized = CalendarBuilder.to_dict(calendar)

    assert serialized["weekly_schedule"] == {"0": [("09:00:15", "18:00:45")]}
    assert serialized["day_overrides"] == {
        "2026-03-02": [("10:30:05", "12:45:10")]
    }
