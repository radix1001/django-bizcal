"""Abstract business calendar interface and shared operations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import OrderedDict
from collections.abc import Iterable, Iterator, Mapping
from datetime import UTC, date, datetime, time, timedelta, tzinfo
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from ..exceptions import CalendarRangeError
from ..intervals import BusinessInterval, normalize_intervals
from ..types import (
    DateInput,
    RenderTzInput,
    TimeInput,
    TzInput,
    coerce_date,
    coerce_zoneinfo,
    ensure_aware,
)
from ..windows import ScheduleBlock

_SEARCH_HORIZON_DAYS = 3660
_LOCAL_DAY_WINDOW_CACHE_SIZE = 512

if TYPE_CHECKING:
    from ..config import DeadlinePolicyConfig
    from ..deadlines import BusinessDeadline
    from ..policies import DeadlinePolicy


class BusinessCalendar(ABC):
    """Abstract calendar returning business intervals in a reference timezone."""

    __slots__ = (
        "_tz",
        "_calendar_name",
        "_local_day_window_cache",
        "_clipped_day_window_cache",
        "_resolved_may_span_midnight",
    )

    def __init__(self, tz: TzInput) -> None:
        self._tz = coerce_zoneinfo(tz)
        self._calendar_name: str | None = None
        self._local_day_window_cache: OrderedDict[date, tuple[BusinessInterval, ...]] = (
            OrderedDict()
        )
        self._clipped_day_window_cache: OrderedDict[date, tuple[BusinessInterval, ...]] = (
            OrderedDict()
        )
        self._resolved_may_span_midnight: bool | None = None

    @property
    def tz(self) -> ZoneInfo:
        """Reference timezone for the calendar."""
        return self._tz

    @property
    def calendar_name(self) -> str | None:
        """Optional logical calendar name, typically attached by Django services."""
        return self._calendar_name

    @abstractmethod
    def _business_windows_for_day_local(self, day: date) -> tuple[BusinessInterval, ...]:
        """Return normalized intervals anchored to a local calendar day.

        Intervals are anchored to the day on which they start and may end after
        midnight. Subclasses that emit such intervals must also return `True` from
        `_may_span_midnight`, so that the public day-oriented API clips them to civil
        days and picks up the previous day's spillover.
        """

    def _may_span_midnight(self) -> bool:
        """Return whether this calendar can emit day intervals that cross midnight.

        Resolved once per instance, since calendars are immutable after construction.
        """
        return False

    def _accepts_spillover_into(self, day: date) -> bool:
        """Return whether the previous day's overnight block may extend into this day."""
        return True

    def business_windows_for_day(
        self,
        day: DateInput,
        *,
        tz: RenderTzInput | None = None,
    ) -> tuple[BusinessInterval, ...]:
        """Return business intervals for a calendar day rendered in the target timezone."""
        target_tz = self.tz if tz is None else _resolve_render_tz(tz)
        target_day = _coerce_day_in_timezone(day, target_tz)
        if target_tz == self.tz:
            return self._clipped_windows_for_day_local(target_day)
        day_start = _local_day_start(target_day, target_tz)
        day_end = _local_day_start(target_day + timedelta(days=1), target_tz)
        return self.business_windows_for_range(day_start, day_end, tz=target_tz)

    def business_windows_for_range(
        self,
        start: datetime,
        end: datetime,
        *,
        tz: RenderTzInput | None = None,
    ) -> tuple[BusinessInterval, ...]:
        """Return normalized business intervals overlapping the given aware datetime range."""
        start = ensure_aware(start, param_name="start")
        end = ensure_aware(end, param_name="end")
        if start > end:
            raise ValueError("start must not be later than end.")
        if start == end:
            return ()
        target_tzinfo = start.tzinfo if tz is None else _resolve_render_tz(tz)
        assert target_tzinfo is not None
        range_start = start.astimezone(target_tzinfo)
        range_end = end.astimezone(target_tzinfo)
        local_start = start.astimezone(self.tz) - timedelta(days=1)
        local_end = end.astimezone(self.tz) + timedelta(days=1)
        range_interval = BusinessInterval(range_start, range_end)
        intervals: list[BusinessInterval] = []
        for current_day in _iter_days(local_start.date(), local_end.date()):
            for interval in self._cached_business_windows_for_day_local(current_day):
                projected = interval.to_timezone(target_tzinfo)
                overlap = projected.intersection(range_interval)
                if overlap is not None:
                    intervals.append(overlap)
        return normalize_intervals(intervals)

    def is_business_day(self, value: DateInput) -> bool:
        """Return whether the given calendar day has at least one business interval.

        A day covered only by the tail of an overnight block started the previous day
        still counts as a business day.
        """
        return bool(self._clipped_windows_for_day_local(_coerce_day_in_timezone(value, self.tz)))

    def iter_business_days(
        self,
        start: DateInput,
        end: DateInput,
        *,
        inclusive: bool = True,
    ) -> Iterator[date]:
        """Iterate over business days between two day-like values."""
        start_day = _coerce_day_in_timezone(start, self.tz)
        end_day = _coerce_day_in_timezone(end, self.tz)
        if start_day > end_day:
            raise ValueError("start must not be later than end.")
        final_day = end_day if inclusive else end_day - timedelta(days=1)
        current_day = start_day
        while current_day <= final_day:
            if self.is_business_day(current_day):
                yield current_day
            current_day += timedelta(days=1)

    def list_business_days(
        self,
        start: DateInput,
        end: DateInput,
        *,
        inclusive: bool = True,
    ) -> list[date]:
        """Return business days between two day-like values as a list."""
        return list(self.iter_business_days(start, end, inclusive=inclusive))

    def count_business_days(
        self,
        start: DateInput,
        end: DateInput,
        *,
        inclusive: bool = True,
    ) -> int:
        """Return the number of business days between two day-like values."""
        return sum(1 for _ in self.iter_business_days(start, end, inclusive=inclusive))

    def next_business_day(self, value: DateInput) -> date:
        """Return the next business day on or after the given day-like value."""
        current_day = _coerce_day_in_timezone(value, self.tz)
        for offset in range(_SEARCH_HORIZON_DAYS):
            day = current_day + timedelta(days=offset)
            if self.is_business_day(day):
                return day
        raise CalendarRangeError("Unable to find the next business day within the search horizon.")

    def previous_business_day(self, value: DateInput) -> date:
        """Return the previous business day on or before the given day-like value."""
        current_day = _coerce_day_in_timezone(value, self.tz)
        for offset in range(_SEARCH_HORIZON_DAYS):
            day = current_day - timedelta(days=offset)
            if self.is_business_day(day):
                return day
        raise CalendarRangeError(
            "Unable to find the previous business day within the search horizon."
        )

    def is_business_time(self, value: datetime) -> bool:
        """Return whether the aware datetime falls inside a business interval."""
        current = ensure_aware(value, param_name="value")
        return any(
            interval.contains(current)
            for interval in self.business_windows_for_day(current, tz=self.tz)
        )

    def opening_for_day(
        self,
        day: DateInput,
        *,
        tz: RenderTzInput | None = None,
    ) -> datetime | None:
        """Return the first opening datetime for the given day, if any."""
        intervals = self.business_windows_for_day(day, tz=tz)
        if not intervals:
            return None
        return intervals[0].start

    def closing_for_day(
        self,
        day: DateInput,
        *,
        tz: RenderTzInput | None = None,
    ) -> datetime | None:
        """Return the final closing datetime for the given day, if any."""
        intervals = self.business_windows_for_day(day, tz=tz)
        if not intervals:
            return None
        return intervals[-1].end

    def next_opening_datetime(self, value: datetime) -> datetime:
        """Return the next opening boundary at or after the given datetime.

        Boundaries are civil-day boundaries: when an overnight block is still open at
        midnight, the reported "opening" for the following day is midnight itself, not
        the wall-clock time at which the block originally started.
        """
        current = ensure_aware(value, param_name="value")
        target_tzinfo = _require_tzinfo(current)
        current = current.astimezone(target_tzinfo)
        day = current.date()
        for _ in range(_SEARCH_HORIZON_DAYS):
            intervals = self.business_windows_for_day(day, tz=target_tzinfo)
            for interval in intervals:
                if current <= interval.start:
                    return interval.start
            day += timedelta(days=1)
            current = _local_day_start(day, target_tzinfo)
        raise CalendarRangeError(
            "Unable to find the next opening datetime within the search horizon."
        )

    def previous_closing_datetime(self, value: datetime) -> datetime:
        """Return the previous closing boundary at or before the given datetime.

        Boundaries are civil-day boundaries: when an overnight block is still open at
        midnight, the reported "closing" for the starting day is midnight itself, not
        the wall-clock time at which the block actually ends.
        """
        current = ensure_aware(value, param_name="value")
        target_tzinfo = _require_tzinfo(current)
        current = current.astimezone(target_tzinfo)
        day = current.date()
        for _ in range(_SEARCH_HORIZON_DAYS):
            intervals = self.business_windows_for_day(day, tz=target_tzinfo)
            for interval in reversed(intervals):
                if current >= interval.end:
                    return interval.end
            day -= timedelta(days=1)
            current = min(current, _local_day_end(day, target_tzinfo))
        raise CalendarRangeError(
            "Unable to find the previous closing datetime within the search horizon."
        )

    def next_business_datetime(self, value: datetime) -> datetime:
        """Return the next business datetime or boundary at or after the given datetime."""
        current = ensure_aware(value, param_name="value")
        target_tzinfo = _require_tzinfo(current)
        current = current.astimezone(target_tzinfo)
        day = current.date()
        for _ in range(_SEARCH_HORIZON_DAYS):
            intervals = self.business_windows_for_day(day, tz=target_tzinfo)
            for interval in intervals:
                if interval.start <= current < interval.end:
                    return current
                if current < interval.start:
                    return interval.start
            day += timedelta(days=1)
            current = _local_day_start(day, target_tzinfo)
        raise CalendarRangeError(
            "Unable to find the next business datetime within the search horizon."
        )

    def previous_business_datetime(self, value: datetime) -> datetime:
        """Return the previous business datetime or closing boundary at or before the input."""
        current = ensure_aware(value, param_name="value")
        target_tzinfo = _require_tzinfo(current)
        current = current.astimezone(target_tzinfo)
        day = current.date()
        for _ in range(_SEARCH_HORIZON_DAYS):
            intervals = self.business_windows_for_day(day, tz=target_tzinfo)
            for interval in reversed(intervals):
                if interval.start <= current <= interval.end:
                    return current
                if current > interval.end:
                    return interval.end
            day -= timedelta(days=1)
            current = min(current, _local_day_end(day, target_tzinfo))
        raise CalendarRangeError(
            "Unable to find the previous business datetime within the search horizon."
        )

    def add_business_time(self, start: datetime, delta: timedelta) -> datetime:
        """Add or subtract business time from a timezone-aware datetime."""
        cursor = ensure_aware(start, param_name="start")
        if delta == timedelta(0):
            return cursor if self.is_business_time(cursor) else self.next_business_datetime(cursor)
        return (
            self._add_positive_business_time(cursor, delta)
            if delta > timedelta(0)
            else self._add_negative_business_time(cursor, -delta)
        )

    def add_business_hours(self, start: datetime, hours: int | float) -> datetime:
        """Add business hours as real elapsed time."""
        return self.add_business_time(start, timedelta(hours=hours))

    def add_business_minutes(self, start: datetime, minutes: int | float) -> datetime:
        """Add business minutes as real elapsed time."""
        return self.add_business_time(start, timedelta(minutes=minutes))

    def deadline_for(
        self,
        start: datetime,
        service_time: timedelta,
        *,
        calendar_name: str | None = None,
    ) -> BusinessDeadline:
        """Compute a business deadline tied to this calendar."""
        from ..deadlines import deadline_for as compute_deadline_for

        return compute_deadline_for(
            start,
            service_time,
            calendar=self,
            calendar_name=calendar_name or self.calendar_name,
        )

    def breach_at(self, start: datetime, service_time: timedelta) -> datetime:
        """Return the breach datetime for a business-time target on this calendar."""
        from ..deadlines import breach_at as compute_breach_at

        return compute_breach_at(start, service_time, calendar=self)

    def resolve_deadline_policy(
        self,
        start: datetime,
        policy: DeadlinePolicy,
        *,
        calendar_name: str | None = None,
    ) -> BusinessDeadline:
        """Resolve a deadline policy on this calendar."""
        return policy.resolve(
            start,
            calendar=self,
            calendar_name=calendar_name or self.calendar_name,
        )

    def resolve_deadline_policy_dict(
        self,
        start: datetime,
        policy_config: DeadlinePolicyConfig | Mapping[str, Any],
        *,
        calendar_name: str | None = None,
    ) -> BusinessDeadline:
        """Build and resolve a declarative deadline policy on this calendar."""
        from ..policies import DeadlinePolicyBuilder

        return DeadlinePolicyBuilder.from_dict(policy_config).resolve(
            start,
            calendar=self,
            calendar_name=calendar_name or self.calendar_name,
        )

    def due_on_next_business_day(
        self,
        day: DateInput,
        *,
        at: str | TimeInput = "opening",
        tz: RenderTzInput | None = None,
    ) -> datetime:
        """Return a due datetime on the next business day for this calendar."""
        from ..deadlines import due_on_next_business_day as compute_due_on_next_business_day

        return compute_due_on_next_business_day(day, calendar=self, at=at, tz=tz)

    def business_deadline_at_close(
        self,
        start_day: DateInput,
        business_days: int,
        *,
        include_start: bool = False,
        tz: RenderTzInput | None = None,
    ) -> datetime:
        """Return the closing boundary after a number of business days on this calendar."""
        from ..deadlines import (
            business_deadline_at_close as compute_business_deadline_at_close,
        )

        return compute_business_deadline_at_close(
            start_day,
            business_days,
            calendar=self,
            include_start=include_start,
            tz=tz,
        )

    def business_time_between(self, start: datetime, end: datetime) -> timedelta:
        """Return the real business time elapsed between two aware datetimes."""
        start = ensure_aware(start, param_name="start")
        end = ensure_aware(end, param_name="end")
        if start == end:
            return timedelta(0)
        if start > end:
            return -self.business_time_between(end, start)
        intervals = self.business_windows_for_range(start, end, tz=self.tz)
        total = timedelta(0)
        for interval in intervals:
            total += interval.duration()
        return total

    def business_minutes_between(self, start: datetime, end: datetime) -> float:
        """Return business time between datetimes expressed in minutes."""
        return self.business_time_between(start, end).total_seconds() / 60.0

    def business_hours_between(self, start: datetime, end: datetime) -> float:
        """Return business time between datetimes expressed in hours."""
        return self.business_time_between(start, end).total_seconds() / 3600.0

    def _add_positive_business_time(self, start: datetime, remaining: timedelta) -> datetime:
        cursor = start if self.is_business_time(start) else self.next_business_datetime(start)
        target_tzinfo = _require_tzinfo(cursor)
        day = cursor.date()
        for _ in range(_SEARCH_HORIZON_DAYS):
            intervals = self.business_windows_for_day(day, tz=target_tzinfo)
            for interval in intervals:
                if cursor < interval.start:
                    cursor = interval.start
                if interval.start <= cursor < interval.end:
                    available = _elapsed_between(cursor, interval.end)
                    if remaining <= available:
                        return _shift_datetime(cursor, remaining)
                    remaining -= available
                    cursor = interval.end
            day += timedelta(days=1)
            cursor = max(cursor, _local_day_start(day, target_tzinfo))
        raise CalendarRangeError("Unable to add business time within the search horizon.")

    def _add_negative_business_time(self, start: datetime, remaining: timedelta) -> datetime:
        cursor = start if self.is_business_time(start) else self.previous_business_datetime(start)
        target_tzinfo = _require_tzinfo(cursor)
        day = cursor.date()
        for _ in range(_SEARCH_HORIZON_DAYS):
            intervals = self.business_windows_for_day(day, tz=target_tzinfo)
            for interval in reversed(intervals):
                segment_end = min(cursor, interval.end)
                if segment_end < interval.start:
                    continue
                available = _elapsed_between(interval.start, segment_end)
                if remaining <= available:
                    return _shift_datetime(segment_end, -remaining)
                remaining -= available
                cursor = interval.start
            day -= timedelta(days=1)
            cursor = min(cursor, _local_day_end(day, target_tzinfo))
        raise CalendarRangeError("Unable to subtract business time within the search horizon.")

    def _clipped_windows_for_day_local(self, day: date) -> tuple[BusinessInterval, ...]:
        """Return the calendar-day coverage in the calendar timezone.

        Blocks that cross midnight are clipped to the civil day, and the tail of the
        previous day's block is included, so adjacent days tile the timeline exactly.
        """
        spans_midnight = self._resolved_may_span_midnight
        if spans_midnight is None:
            spans_midnight = self._resolved_may_span_midnight = self._may_span_midnight()
        if not spans_midnight:
            return self._cached_business_windows_for_day_local(day)
        cached = self._clipped_day_window_cache.get(day)
        if cached is not None:
            self._clipped_day_window_cache.move_to_end(day)
            return cached
        windows = self._compute_clipped_windows_for_day_local(day)
        self._clipped_day_window_cache[day] = windows
        if len(self._clipped_day_window_cache) > _LOCAL_DAY_WINDOW_CACHE_SIZE:
            self._clipped_day_window_cache.popitem(last=False)
        return windows

    def _compute_clipped_windows_for_day_local(self, day: date) -> tuple[BusinessInterval, ...]:
        bounds = BusinessInterval(
            start=_local_day_start(day, self.tz),
            end=_local_day_end(day, self.tz),
        )
        clipped: list[BusinessInterval] = []
        if self._accepts_spillover_into(day):
            previous_day = day - timedelta(days=1)
            for interval in self._cached_business_windows_for_day_local(previous_day):
                overlap = interval.intersection(bounds)
                if overlap is not None:
                    clipped.append(overlap)
        for interval in self._cached_business_windows_for_day_local(day):
            overlap = interval.intersection(bounds)
            if overlap is not None:
                clipped.append(overlap)
        return normalize_intervals(clipped)

    def _cached_business_windows_for_day_local(self, day: date) -> tuple[BusinessInterval, ...]:
        cached = self._local_day_window_cache.get(day)
        if cached is not None:
            self._local_day_window_cache.move_to_end(day)
            return cached
        windows = self._business_windows_for_day_local(day)
        self._local_day_window_cache[day] = windows
        if len(self._local_day_window_cache) > _LOCAL_DAY_WINDOW_CACHE_SIZE:
            self._local_day_window_cache.popitem(last=False)
        return windows


def materialize_schedule_blocks(
    day: date,
    blocks: Iterable[ScheduleBlock],
    tz: tzinfo,
) -> tuple[BusinessInterval, ...]:
    """Materialize schedule blocks anchored to a local day into aware intervals.

    Blocks built by `build_schedule_blocks` are already ordered and merged as far as one
    day allows, so the intervals only need a normalization pass when a block crosses
    midnight and can therefore still overlap a later block on the same anchor day.
    """
    intervals: list[BusinessInterval] = []
    spans_midnight = False
    for block in blocks:
        spans_midnight = spans_midnight or block.spans_midnight
        intervals.append(
            BusinessInterval(
                start=datetime.combine(day, block.start, tzinfo=tz),
                end=datetime.combine(
                    day + timedelta(days=block.end_offset_days),
                    block.end,
                    tzinfo=tz,
                ),
            )
        )
    return normalize_intervals(intervals) if spans_midnight else tuple(intervals)


def _require_tzinfo(value: datetime) -> tzinfo:
    """Return the datetime's timezone, which callers have already ensured is set."""
    current = value.tzinfo
    assert current is not None
    return current


def _local_day_start(day: date, tzinfo: tzinfo) -> datetime:
    """Return the instant at which the given local calendar day starts.

    Normalizing through UTC keeps the returned wall clock valid when local midnight
    does not exist because of a DST forward transition.
    """
    return datetime.combine(day, time.min, tzinfo=tzinfo).astimezone(UTC).astimezone(tzinfo)


def _local_day_end(day: date, tzinfo: tzinfo) -> datetime:
    """Return the exclusive end instant of the given local calendar day."""
    return _local_day_start(day + timedelta(days=1), tzinfo)


def _iter_days(start: date, end: date) -> tuple[date, ...]:
    days: list[date] = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return tuple(days)


def _coerce_day_in_timezone(value: DateInput, tzinfo: tzinfo) -> date:
    if isinstance(value, datetime):
        current = (
            ensure_aware(value, param_name="value")
            if value.tzinfo
            else value.replace(tzinfo=tzinfo)
        )
        return current.astimezone(tzinfo).date()
    return coerce_date(value)


def _elapsed_between(start: datetime, end: datetime) -> timedelta:
    return end.astimezone(UTC) - start.astimezone(UTC)


def _shift_datetime(value: datetime, delta: timedelta) -> datetime:
    return (value.astimezone(UTC) + delta).astimezone(value.tzinfo)


def _resolve_render_tz(value: RenderTzInput) -> tzinfo:
    if isinstance(value, str):
        return coerce_zoneinfo(value)
    return value
