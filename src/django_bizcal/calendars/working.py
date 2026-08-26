"""Working calendar backed by weekday schedules and holiday providers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date

from ..exceptions import ValidationError
from ..intervals import BusinessInterval
from ..providers import (
    CompositeHolidayProvider,
    HolidayProvider,
    HolidaysProvider,
    SetHolidayProvider,
)
from ..types import DateInput, TzInput, Weekday, coerce_date, coerce_years
from ..windows import ScheduleBlock, ScheduleBlockInput, build_schedule_blocks
from .base import BusinessCalendar, materialize_schedule_blocks

WeeklyScheduleInput = Mapping[Weekday | str, Iterable[ScheduleBlockInput]]
DayOverrideInput = Mapping[DateInput, Iterable[ScheduleBlockInput] | None]


class WorkingCalendar(BusinessCalendar):
    """Business calendar with a weekly schedule, holiday provider, and per-day overrides."""

    __slots__ = (
        "_weekly_schedule",
        "_holiday_provider",
        "_day_overrides",
        "_name",
        "_holiday_truncates_overnight",
        "_spans_midnight",
    )

    def __init__(
        self,
        *,
        tz: TzInput,
        weekly_schedule: WeeklyScheduleInput,
        holiday_provider: HolidayProvider | None = None,
        day_overrides: DayOverrideInput | None = None,
        name: str | None = None,
        holiday_truncates_overnight: bool = False,
    ) -> None:
        super().__init__(tz)
        self._weekly_schedule = _normalize_weekly_schedule(weekly_schedule)
        self._holiday_provider = holiday_provider
        self._day_overrides = _normalize_day_overrides(day_overrides)
        self._name = name
        self._holiday_truncates_overnight = bool(holiday_truncates_overnight)
        self._spans_midnight = any(
            block.spans_midnight
            for blocks in (*self._weekly_schedule.values(), *self._day_overrides.values())
            for block in blocks
        )

    @property
    def weekly_schedule(self) -> Mapping[int, tuple[ScheduleBlock, ...]]:
        """Normalized weekly schedule keyed by ISO weekday numbers Monday=0."""
        return self._weekly_schedule

    @property
    def holiday_provider(self) -> HolidayProvider | None:
        """Holiday provider associated with the calendar."""
        return self._holiday_provider

    @property
    def day_overrides(self) -> Mapping[date, tuple[ScheduleBlock, ...]]:
        """Explicit day substitutions where an empty tuple means fully closed."""
        return self._day_overrides

    @property
    def name(self) -> str | None:
        """Optional logical name for diagnostics and documentation."""
        return self._name

    @property
    def holiday_truncates_overnight(self) -> bool:
        """Whether a closed day also suppresses the previous day's overnight block."""
        return self._holiday_truncates_overnight

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
        holiday_truncates_overnight: bool = False,
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
            holiday_truncates_overnight=holiday_truncates_overnight,
        )

    def business_blocks_for_day(self, day: DateInput) -> tuple[BusinessInterval, ...]:
        """Return whole work blocks anchored to the day on which they start.

        Unlike `business_windows_for_day`, the returned intervals are not clipped at
        midnight, so an overnight block queried on its starting day ends at its real
        closing time on the following day. Rendered in the calendar timezone.
        """
        return self._cached_business_windows_for_day_local(coerce_date(day))

    def _business_windows_for_day_local(self, day: date) -> tuple[BusinessInterval, ...]:
        return materialize_schedule_blocks(day, self._resolve_day_windows(day), self.tz)

    def _resolve_day_windows(self, day: date) -> tuple[ScheduleBlock, ...]:
        if day in self.day_overrides:
            return self.day_overrides[day]
        if self.holiday_provider is not None and self.holiday_provider.is_holiday(day):
            return ()
        return self.weekly_schedule.get(day.weekday(), ())

    def _may_span_midnight(self) -> bool:
        return self._spans_midnight

    def _accepts_spillover_into(self, day: date) -> bool:
        if not self._holiday_truncates_overnight:
            return True
        return not self._is_explicitly_closed(day)

    def _is_explicitly_closed(self, day: date) -> bool:
        """Return whether the day is closed by an explicit override or a holiday.

        A weekday that simply has no scheduled block is not "explicitly closed": an
        overnight block started the previous day still spills into it.
        """
        if day in self.day_overrides:
            return not self.day_overrides[day]
        return self.holiday_provider is not None and self.holiday_provider.is_holiday(day)


def _normalize_weekly_schedule(
    schedule: WeeklyScheduleInput,
) -> dict[int, tuple[ScheduleBlock, ...]]:
    normalized: dict[int, tuple[ScheduleBlock, ...]] = {}
    for key, values in schedule.items():
        weekday = int(key)
        if weekday < 0 or weekday > 6:
            raise ValidationError(f"Weekday {weekday!r} is outside the allowed range 0..6.")
        normalized[weekday] = build_schedule_blocks(values)
    return normalized


def _normalize_day_overrides(
    overrides: DayOverrideInput | None,
) -> dict[date, tuple[ScheduleBlock, ...]]:
    if overrides is None:
        return {}
    normalized: dict[date, tuple[ScheduleBlock, ...]] = {}
    for key, values in overrides.items():
        current_day = coerce_date(key)
        normalized[current_day] = () if values is None else build_schedule_blocks(values)
    return normalized
