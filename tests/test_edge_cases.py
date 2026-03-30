from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from django_bizcal import (
    CalendarBuilder,
    DifferenceCalendar,
    IntersectionCalendar,
    OverrideCalendar,
    TimeWindow,
    UnionCalendar,
    WorkingCalendar,
)
from django_bizcal.calendars.base import _coerce_day_in_timezone, _resolve_render_tz
from django_bizcal.exceptions import CalendarConfigurationError, CalendarRangeError, ValidationError
from django_bizcal.intervals import BusinessInterval
from django_bizcal.providers import HolidaysProvider
from django_bizcal.settings import _resolve_preload_years
from django_bizcal.types import coerce_date, coerce_time, coerce_years, ensure_aware, timezone_key


def test_union_and_intersection_require_children() -> None:
    with pytest.raises(ValidationError):
        UnionCalendar([])
    with pytest.raises(ValidationError):
        IntersectionCalendar([])


def test_override_builder_and_difference_builder_with_explicit_operands() -> None:
    override = CalendarBuilder.from_dict(
        {
            "type": "override",
            "tz": "UTC",
            "base": {
                "type": "working",
                "tz": "UTC",
                "weekly_schedule": {"0": [["09:00", "18:00"]]},
            },
            "overrides": {
                "2026-03-02": [["10:00", "12:00"]],
            },
        }
    )
    assert isinstance(override, OverrideCalendar)
    assert len(override.business_windows_for_day("2026-03-02")) == 1

    difference = CalendarBuilder.from_dict(
        {
            "type": "difference",
            "tz": "UTC",
            "base": {
                "type": "working",
                "tz": "UTC",
                "weekly_schedule": {"0": [["09:00", "18:00"]]},
            },
            "subtract": {
                "type": "working",
                "tz": "UTC",
                "weekly_schedule": {"0": [["12:00", "13:00"]]},
            },
        }
    )
    assert isinstance(difference, DifferenceCalendar)
    assert len(difference.business_windows_for_day("2026-03-02")) == 2


def test_builder_uses_default_context_and_custom_holidays() -> None:
    calendar = CalendarBuilder.from_dict(
        {
            "type": "working",
            "weekly_schedule": {"0": [["09:00", "18:00"]]},
            "custom_holidays": ["2026-03-02"],
        },
        default_tz="UTC",
        default_country="CL",
        preload_years=[2026],
    )
    assert calendar.tz.key == "UTC"
    assert calendar.is_business_day(date(2026, 3, 2)) is False


def test_builder_rejects_missing_type_and_invalid_shapes() -> None:
    with pytest.raises(CalendarConfigurationError):
        CalendarBuilder.from_dict({})
    with pytest.raises(CalendarConfigurationError):
        CalendarBuilder.from_dict(
            {
                "type": "working",
                "weekly_schedule": {"0": [["09:00", "18:00"]]},
            }
        )
    with pytest.raises(CalendarConfigurationError):
        CalendarBuilder.from_dict({"type": "union", "children": "invalid"})
    with pytest.raises(CalendarConfigurationError):
        CalendarBuilder.from_dict(
            {
                "type": "override",
                "base": {
                    "type": "working",
                    "tz": "UTC",
                    "weekly_schedule": {"0": [["09:00", "18:00"]]},
                },
                "overrides": [],
            }
        )
    with pytest.raises(CalendarConfigurationError):
        CalendarBuilder.from_dict(
            {
                "type": "difference",
                "children": [
                    {
                        "type": "working",
                        "tz": "UTC",
                        "weekly_schedule": {"0": [["09:00", "18:00"]]},
                    },
                ],
            }
        )


def test_business_calendar_range_helpers_cover_empty_and_invalid_ranges() -> None:
    calendar = WorkingCalendar(tz="UTC", weekly_schedule={0: [("09:00", "18:00")]})
    monday = datetime(2026, 3, 2, 9, 0, tzinfo=ZoneInfo("UTC"))
    assert calendar.business_windows_for_range(monday, monday) == ()
    with pytest.raises(ValueError):
        calendar.business_windows_for_range(
            datetime(2026, 3, 2, 10, 0, tzinfo=ZoneInfo("UTC")),
            datetime(2026, 3, 2, 9, 0, tzinfo=ZoneInfo("UTC")),
        )


def test_add_business_time_zero_and_reverse_queries() -> None:
    calendar = WorkingCalendar(tz="UTC", weekly_schedule={0: [("09:00", "18:00")]})
    outside = datetime(2026, 3, 2, 8, 0, tzinfo=ZoneInfo("UTC"))
    assert calendar.add_business_time(outside, timedelta(0)) == datetime(
        2026,
        3,
        2,
        9,
        0,
        tzinfo=ZoneInfo("UTC"),
    )
    assert calendar.business_minutes_between(outside, outside) == 0.0


def test_dst_backward_interval_duration_reflects_extra_hour() -> None:
    calendar = WorkingCalendar(
        tz="America/New_York",
        weekly_schedule={6: [("00:30", "02:30")]},
    )
    windows = calendar.business_windows_for_day(date(2026, 11, 1))
    assert len(windows) == 1
    assert windows[0].duration() == timedelta(hours=3)


def test_holidays_provider_requires_years_when_instantiated_directly() -> None:
    with pytest.raises(CalendarRangeError):
        HolidaysProvider(country="CL", years=())


def test_holiday_provider_composition_handles_empty_provider_tuple() -> None:
    from django_bizcal.providers import CompositeHolidayProvider

    provider = CompositeHolidayProvider(providers=())
    assert provider.providers == ()


def test_internal_type_coercion_helpers_validate_inputs() -> None:
    assert coerce_date(datetime(2026, 3, 2, 10, 0, tzinfo=ZoneInfo("UTC"))) == date(2026, 3, 2)
    assert coerce_date("2026-03-02") == date(2026, 3, 2)
    assert coerce_time("09:15").hour == 9
    assert coerce_years(2026) == (2026,)
    assert coerce_years(None) == ()
    assert coerce_years([2027, 2026, 2026]) == (2026, 2027)
    assert timezone_key(ZoneInfo("UTC")) == "UTC"
    assert _resolve_render_tz("UTC").tzname(None) == "UTC"
    assert _coerce_day_in_timezone(
        datetime(2026, 3, 2, 23, 30, tzinfo=ZoneInfo("UTC")),
        ZoneInfo("America/Santiago"),
    ) == date(2026, 3, 2)

    with pytest.raises(ValidationError):
        coerce_date("bad-date")
    with pytest.raises(ValidationError):
        coerce_time("bad-time")
    with pytest.raises(ValidationError):
        coerce_years([])
    with pytest.raises(ValidationError):
        ensure_aware(datetime(2026, 3, 2, 9, 0), param_name="value")


def test_interval_and_window_edge_operations() -> None:
    with pytest.raises(ValidationError):
        BusinessInterval(
            datetime(2026, 3, 2, 10, 0, tzinfo=ZoneInfo("UTC")),
            datetime(2026, 3, 2, 9, 0, tzinfo=ZoneInfo("UTC")),
        )

    interval = BusinessInterval(
        datetime(2026, 3, 2, 9, 0, tzinfo=ZoneInfo("UTC")),
        datetime(2026, 3, 2, 12, 0, tzinfo=ZoneInfo("UTC")),
    )
    overlap = BusinessInterval(
        datetime(2026, 3, 2, 11, 0, tzinfo=ZoneInfo("UTC")),
        datetime(2026, 3, 2, 13, 0, tzinfo=ZoneInfo("UTC")),
    )
    disjoint = BusinessInterval(
        datetime(2026, 3, 2, 14, 0, tzinfo=ZoneInfo("UTC")),
        datetime(2026, 3, 2, 15, 0, tzinfo=ZoneInfo("UTC")),
    )
    assert interval.contains(datetime(2026, 3, 2, 9, 30, tzinfo=ZoneInfo("UTC"))) is True
    assert interval.overlaps(overlap) is True
    assert interval.intersection(overlap) is not None
    assert len(interval.subtract(overlap)) == 1
    assert interval.subtract(disjoint) == (interval,)
    with pytest.raises(ValidationError):
        interval.merge(disjoint)

    shifted = BusinessInterval.to_timezone(interval, ZoneInfo("America/Santiago"))
    assert shifted.start.tzinfo is not None

    from django_bizcal.intervals import normalize_intervals

    assert normalize_intervals([]) == ()

    left = TimeWindow.from_pair(time(9, 0), time(10, 0))
    right = TimeWindow.from_pair(time(10, 30), time(11, 0))
    assert left.duration() == timedelta(hours=1)
    assert left.contains(time(9, 30)) is True
    assert left.overlaps(right) is False
    with pytest.raises(ValidationError):
        left.merge(right)

    from django_bizcal.windows import intersect_time_windows, normalize_time_windows

    assert normalize_time_windows([]) == ()
    assert intersect_time_windows([left], [right]) == ()


def test_preload_years_validation() -> None:
    tz = ZoneInfo("UTC")
    years = _resolve_preload_years(3, tz)
    assert len(years) == 3
    with pytest.raises(ValueError):
        _resolve_preload_years(0, tz)
    with pytest.raises(ValueError):
        _resolve_preload_years([], tz)


def test_working_calendar_properties_and_validation_branches() -> None:
    calendar = WorkingCalendar.from_country(
        country="CL",
        years=2026,
        tz="UTC",
        weekly_schedule={0: [("09:00", "18:00")]},
    )
    assert calendar.name == "CL"
    assert calendar.holiday_provider is not None

    with pytest.raises(ValidationError):
        WorkingCalendar(tz="UTC", weekly_schedule={7: [("09:00", "18:00")]})


def test_composite_calendar_properties_and_fallback_path() -> None:
    base = WorkingCalendar(tz="UTC", weekly_schedule={0: [("09:00", "18:00")]})
    blocked = WorkingCalendar(tz="UTC", weekly_schedule={0: [("09:00", "18:00")]})
    difference = DifferenceCalendar(base, blocked, tz="UTC")
    override = OverrideCalendar(base, overrides={}, tz="UTC")
    assert difference.base is base
    assert difference.subtract is blocked
    assert override.base is base
    assert override.business_windows_for_day("2026-03-02") == base.business_windows_for_day(
        "2026-03-02"
    )

    empty_overlap = IntersectionCalendar(
        [
            WorkingCalendar(tz="UTC", weekly_schedule={0: [("09:00", "10:00")]}),
            WorkingCalendar(tz="UTC", weekly_schedule={0: [("11:00", "12:00")]}),
        ],
        tz="UTC",
    )
    assert empty_overlap.business_windows_for_day("2026-03-02") == ()
