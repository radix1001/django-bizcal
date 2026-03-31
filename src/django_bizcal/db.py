"""Django database-backed holiday helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import cached_property
from typing import cast

from .calendars.base import BusinessCalendar
from .calendars.composite import OverrideCalendar, OverrideInput
from .exceptions import ValidationError
from .models import CalendarDayOverride, CalendarHoliday
from .windows import TimeWindow, build_time_windows


@dataclass(frozen=True)
class DatabaseHolidayProvider:
    """Holiday provider backed by persisted `CalendarHoliday` rows."""

    calendar_name: str
    using: str = "default"
    include_inactive: bool = False

    def __post_init__(self) -> None:
        if not self.calendar_name.strip():
            raise ValidationError("DatabaseHolidayProvider requires a non-empty calendar_name.")

    @cached_property
    def days(self) -> frozenset[date]:
        """Materialized holiday dates for the configured logical calendar."""
        queryset = CalendarHoliday.objects.using(self.using).filter(
            calendar_name=self.calendar_name
        )
        if not self.include_inactive:
            queryset = queryset.filter(is_active=True)
        return frozenset(queryset.values_list("day", flat=True))

    def is_holiday(self, day: date) -> bool:
        """Return whether the given day is configured as a persisted holiday."""
        return day in self.days


@dataclass(frozen=True)
class DatabaseDayOverrideProvider:
    """Per-day override provider backed by persisted intraday window rows."""

    calendar_name: str
    using: str = "default"
    include_inactive: bool = False

    def __post_init__(self) -> None:
        if not self.calendar_name.strip():
            raise ValidationError("DatabaseDayOverrideProvider requires a non-empty calendar_name.")

    @cached_property
    def overrides(self) -> dict[date, tuple[TimeWindow, ...]]:
        """Materialized per-day override windows keyed by logical calendar day."""
        queryset = (
            CalendarDayOverride.objects.using(self.using)
            .filter(calendar_name=self.calendar_name)
            .prefetch_related("windows")
        )
        if not self.include_inactive:
            queryset = queryset.filter(is_active=True)
        return {
            override.day: build_time_windows(
                (window.start_time, window.end_time)
                for window in override.windows.all().order_by("position", "start_time")
            )
            for override in queryset
        }


def apply_database_holiday_overrides(
    calendar: BusinessCalendar,
    *,
    calendar_name: str,
    using: str = "default",
) -> BusinessCalendar:
    """Wrap a calendar with persisted full-day closures for the named calendar."""
    provider = DatabaseHolidayProvider(calendar_name=calendar_name, using=using)
    if not provider.days:
        return calendar
    return OverrideCalendar(
        calendar,
        overrides={day: None for day in sorted(provider.days)},
        tz=calendar.tz,
    )


def build_database_override_map(
    *,
    calendar_name: str,
    using: str = "default",
) -> dict[date, tuple[TimeWindow, ...] | None]:
    """Return merged persisted overrides for a logical calendar name.

    Persisted day overrides take precedence over full-day holiday closures on the same date.
    """
    holiday_provider = DatabaseHolidayProvider(calendar_name=calendar_name, using=using)
    day_override_provider = DatabaseDayOverrideProvider(calendar_name=calendar_name, using=using)
    overrides: dict[date, tuple[TimeWindow, ...] | None] = {
        day: None for day in sorted(holiday_provider.days)
    }
    overrides.update(day_override_provider.overrides)
    return overrides


def apply_database_overrides(
    calendar: BusinessCalendar,
    *,
    calendar_name: str,
    using: str = "default",
) -> BusinessCalendar:
    """Wrap a calendar with all persisted full-day and intraday day overrides."""
    overrides = build_database_override_map(calendar_name=calendar_name, using=using)
    if not overrides:
        return calendar
    return OverrideCalendar(calendar, overrides=cast(OverrideInput, overrides), tz=calendar.tz)
