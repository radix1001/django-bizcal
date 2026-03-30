"""Django database-backed holiday helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import cached_property

from .calendars.base import BusinessCalendar
from .calendars.composite import OverrideCalendar
from .exceptions import ValidationError
from .models import CalendarHoliday


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
