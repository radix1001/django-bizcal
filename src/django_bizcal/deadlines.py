"""Deadline and SLA-oriented helpers built on top of business calendars."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from .calendars.base import BusinessCalendar, _resolve_render_tz
from .exceptions import ValidationError
from .intervals import BusinessInterval
from .types import DateInput, RenderTzInput, TimeInput, coerce_date, coerce_time, ensure_aware


@dataclass(frozen=True, slots=True)
class BusinessDeadline:
    """Computed business deadline tied to a concrete calendar."""

    start: datetime
    service_time: timedelta
    deadline: datetime
    calendar: BusinessCalendar
    calendar_name: str | None = None

    def __post_init__(self) -> None:
        start = ensure_aware(self.start, param_name="start")
        deadline = ensure_aware(self.deadline, param_name="deadline")
        if self.service_time < timedelta(0):
            raise ValidationError("service_time must not be negative.")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "deadline", deadline)
        if self.calendar_name is not None:
            normalized_name = str(self.calendar_name).strip()
            if not normalized_name:
                raise ValidationError("calendar_name must not be blank when provided.")
            object.__setattr__(self, "calendar_name", normalized_name)

    def remaining(self, *, at: datetime | None = None) -> timedelta:
        """Return signed remaining business time until the deadline."""
        current = _resolve_reference_datetime(at, self.deadline)
        return self.calendar.business_time_between(current, self.deadline)

    def remaining_minutes(self, *, at: datetime | None = None) -> float:
        """Return signed remaining business time in minutes."""
        return self.remaining(at=at).total_seconds() / 60.0

    def remaining_hours(self, *, at: datetime | None = None) -> float:
        """Return signed remaining business time in hours."""
        return self.remaining(at=at).total_seconds() / 3600.0

    def is_breached(self, *, at: datetime | None = None) -> bool:
        """Return whether the deadline has already been breached."""
        return self.remaining(at=at) < timedelta(0)


def deadline_for(
    start: datetime,
    service_time: timedelta,
    *,
    calendar: BusinessCalendar,
    calendar_name: str | None = None,
) -> BusinessDeadline:
    """Compute a business deadline by adding service time on top of a calendar."""
    normalized_start = ensure_aware(start, param_name="start")
    if service_time < timedelta(0):
        raise ValidationError("service_time must not be negative.")
    deadline = calendar.add_business_time(normalized_start, service_time)
    return BusinessDeadline(
        start=normalized_start,
        service_time=service_time,
        deadline=deadline,
        calendar=calendar,
        calendar_name=calendar_name or calendar.calendar_name,
    )


def breach_at(
    start: datetime,
    service_time: timedelta,
    *,
    calendar: BusinessCalendar,
) -> datetime:
    """Return the breach datetime for a business-time target."""
    return deadline_for(
        start,
        service_time,
        calendar=calendar,
    ).deadline


def remaining_business_time(
    deadline: BusinessDeadline | datetime,
    *,
    calendar: BusinessCalendar | None = None,
    now: datetime | None = None,
) -> timedelta:
    """Return signed remaining business time for a deadline."""
    resolved_deadline = _coerce_deadline(deadline, calendar=calendar)
    return resolved_deadline.remaining(at=now)


def is_breached(
    deadline: BusinessDeadline | datetime,
    *,
    calendar: BusinessCalendar | None = None,
    now: datetime | None = None,
) -> bool:
    """Return whether a deadline has already been breached."""
    resolved_deadline = _coerce_deadline(deadline, calendar=calendar)
    return resolved_deadline.is_breached(at=now)


def due_on_next_business_day(
    day: DateInput,
    *,
    calendar: BusinessCalendar,
    at: str | TimeInput = "opening",
    tz: RenderTzInput | None = None,
) -> datetime:
    """Return a deadline on the next business day after the given day-like value."""
    local_day = _coerce_local_day(day, calendar)
    target_day = calendar.next_business_day(local_day + timedelta(days=1))
    return _resolve_day_deadline(target_day, calendar=calendar, at=at, tz=tz)


def business_deadline_at_close(
    start_day: DateInput,
    business_days: int,
    *,
    calendar: BusinessCalendar,
    include_start: bool = False,
    tz: RenderTzInput | None = None,
) -> datetime:
    """Return the closing boundary after a number of business days."""
    if business_days <= 0:
        raise ValidationError("business_days must be a positive integer.")
    local_day = _coerce_local_day(start_day, calendar)
    target_day = (
        calendar.next_business_day(local_day)
        if include_start
        else calendar.next_business_day(local_day + timedelta(days=1))
    )
    remaining_days = business_days - 1
    while remaining_days > 0:
        target_day = calendar.next_business_day(target_day + timedelta(days=1))
        remaining_days -= 1
    return _resolve_day_deadline(target_day, calendar=calendar, at="closing", tz=tz)


def _resolve_reference_datetime(value: datetime | None, deadline: datetime) -> datetime:
    if value is None:
        return datetime.now(deadline.tzinfo)
    return ensure_aware(value, param_name="at")


def _coerce_deadline(
    value: BusinessDeadline | datetime,
    *,
    calendar: BusinessCalendar | None,
) -> BusinessDeadline:
    if isinstance(value, BusinessDeadline):
        if calendar is not None:
            raise ValidationError(
                "calendar must not be provided when deadline is already a BusinessDeadline."
            )
        return value
    if calendar is None:
        raise ValidationError("calendar is required when deadline is a datetime.")
    return BusinessDeadline(
        start=value,
        service_time=timedelta(0),
        deadline=ensure_aware(value, param_name="deadline"),
        calendar=calendar,
    )


def _coerce_local_day(value: DateInput, calendar: BusinessCalendar) -> date:
    if isinstance(value, datetime):
        current = value if value.tzinfo is not None else value.replace(tzinfo=calendar.tz)
        return current.astimezone(calendar.tz).date()
    return coerce_date(value)


def _resolve_day_deadline(
    day: date,
    *,
    calendar: BusinessCalendar,
    at: str | TimeInput,
    tz: RenderTzInput | None,
) -> datetime:
    intervals = calendar.business_windows_for_day(day, tz=calendar.tz)
    if not intervals:
        raise ValidationError("Resolved day does not contain business windows.")
    if at == "opening":
        resolved = intervals[0].start
    elif at == "closing":
        resolved = intervals[-1].end
    else:
        candidate = datetime.combine(day, _coerce_deadline_time(at), tzinfo=calendar.tz)
        resolved = _snap_candidate_within_day(candidate, intervals)
    if tz is None:
        return resolved
    return resolved.astimezone(_resolve_render_tz(tz))


def _coerce_deadline_time(value: TimeInput) -> time:
    return coerce_time(value)


def _snap_candidate_within_day(
    candidate: datetime,
    intervals: tuple[BusinessInterval, ...],
) -> datetime:
    for interval in intervals:
        if candidate <= interval.start:
            return interval.start
        if interval.start <= candidate <= interval.end:
            return candidate
    return intervals[-1].end
