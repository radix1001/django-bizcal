"""Working calendar backed by weekday schedules and holiday providers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime

from ..exceptions import ValidationError
from ..intervals import BusinessInterval
from ..providers import (
    CompositeHolidayProvider,
    HolidayProvider,
    HolidaysProvider,
    SetHolidayProvider,
)
from ..types import DateInput, TimeInput, TzInput, Weekday, coerce_date, coerce_years
from ..windows import TimeWindow, build_time_windows
from .base import BusinessCalendar

WeeklyScheduleInput = Mapping[
    Weekday | str,
    Iterable[tuple[TimeInput, TimeInput] | TimeWindow],
]
DayOverrideInput = Mapping[DateInput, Iterable[tuple[TimeInput, TimeInput] | TimeWindow] | None]


class WorkingCalendar(BusinessCalendar):
    """Business calendar with a weekly schedule, holiday provider, and per-day overrides."""

    __slots__ = ("_weekly_schedule", "_holiday_provider", "_day_overrides", "_name")

    def __init__(
        self,
        *,
        tz: TzInput,
        weekly_schedule: WeeklyScheduleInput,
        holiday_provider: HolidayProvider | None = None,
        day_overrides: DayOverrideInput | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(tz)
        self._weekly_schedule = _normalize_weekly_schedule(weekly_schedule)
        self._holiday_provider = holiday_provider
        self._day_overrides = _normalize_day_overrides(day_overrides)
        self._name = name

    @property
    def weekly_schedule(self) -> Mapping[int, tuple[TimeWindow, ...]]:
        """Normalized weekly schedule keyed by ISO weekday numbers Monday=0."""
        return self._weekly_schedule

    @property
    def holiday_provider(self) -> HolidayProvider | None:
        """Holiday provider associated with the calendar."""
        return self._holiday_provider

    @property
    def day_overrides(self) -> Mapping[date, tuple[TimeWindow, ...]]:
        """Explicit day substitutions where an empty tuple means fully closed."""
        return self._day_overrides

    @property
    def name(self) -> str | None:
        """Optional logical name for diagnostics and documentation."""
        return self._name

    @classmethod
    def from_country(
        cls,
        *,
        country: str,
        years: int | Iterable[int],
        tz: TzInput,
        weekly_schedule: WeeklyScheduleInput,
        subdivision: str | None = None,
        observed: bool = True,
        extra_holidays: Iterable[DateInput] | None = None,
        day_overrides: DayOverrideInput | None = None,
        name: str | None = None,
    ) -> WorkingCalendar:
        """Build a calendar with official holidays plus optional custom holidays."""
        official = HolidaysProvider.from_country(
            country=country,
            years=coerce_years(tuple(years) if not isinstance(years, int) else years),
            subdivision=subdivision,
            observed=observed,
        )
        extra = SetHolidayProvider.from_dates(extra_holidays or ())
        provider = CompositeHolidayProvider.combine([official, extra])
        return cls(
            tz=tz,
            weekly_schedule=weekly_schedule,
            holiday_provider=provider,
            day_overrides=day_overrides,
            name=name or country,
        )

    def _business_windows_for_day_local(self, day: date) -> tuple[BusinessInterval, ...]:
        windows = self._resolve_day_windows(day)
        return tuple(
            BusinessInterval(
                start=datetime.combine(day, window.start, tzinfo=self.tz),
                end=datetime.combine(day, window.end, tzinfo=self.tz),
            )
            for window in windows
        )

    def _resolve_day_windows(self, day: date) -> tuple[TimeWindow, ...]:
        if day in self.day_overrides:
            return self.day_overrides[day]
        if self.holiday_provider is not None and self.holiday_provider.is_holiday(day):
            return ()
        return self.weekly_schedule.get(day.weekday(), ())


def _normalize_weekly_schedule(schedule: WeeklyScheduleInput) -> dict[int, tuple[TimeWindow, ...]]:
    normalized: dict[int, tuple[TimeWindow, ...]] = {}
    for key, values in schedule.items():
        weekday = int(key)
        if weekday < 0 or weekday > 6:
            raise ValidationError(f"Weekday {weekday!r} is outside the allowed range 0..6.")
        normalized[weekday] = build_time_windows(values)
    return normalized


def _normalize_day_overrides(
    overrides: DayOverrideInput | None,
) -> dict[date, tuple[TimeWindow, ...]]:
    if overrides is None:
        return {}
    normalized: dict[date, tuple[TimeWindow, ...]] = {}
    for key, values in overrides.items():
        current_day = coerce_date(key)
        normalized[current_day] = () if values is None else build_time_windows(values)
    return normalized
