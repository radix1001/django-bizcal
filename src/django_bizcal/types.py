"""Internal typing helpers and normalization utilities."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date, datetime, time, tzinfo
from zoneinfo import ZoneInfo

from .exceptions import ValidationError

DateInput = date | datetime | str
TimeInput = time | str
TzInput = ZoneInfo | str
RenderTzInput = ZoneInfo | tzinfo | str
Weekday = int


def coerce_zoneinfo(value: TzInput) -> ZoneInfo:
    """Return a ZoneInfo instance from a ZoneInfo or timezone key."""
    if isinstance(value, ZoneInfo):
        return value
    return ZoneInfo(value)


def coerce_date(value: DateInput) -> date:
    """Return a date from date-like values."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"Invalid ISO date value: {value!r}") from exc


def coerce_time(value: TimeInput) -> time:
    """Return a time from a time object or HH:MM[:SS] string."""
    if isinstance(value, time):
        return value.replace(microsecond=0)
    try:
        parsed = time.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError(f"Invalid ISO time value: {value!r}") from exc
    return parsed.replace(microsecond=0)


def coerce_years(value: int | Sequence[int] | None) -> tuple[int, ...]:
    """Normalize configured years into an ordered tuple."""
    if value is None:
        return ()
    years: Iterable[int]
    if isinstance(value, int):
        years = [value]
    else:
        years = value
    normalized = tuple(sorted({int(year) for year in years}))
    if not normalized:
        raise ValidationError("At least one year must be provided when years are configured.")
    return normalized


def ensure_aware(value: datetime, *, param_name: str) -> datetime:
    """Ensure that a datetime is timezone-aware."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValidationError(f"{param_name} must be timezone-aware.")
    return value


def timezone_key(value: tzinfo) -> str:
    """Best-effort stable key for a timezone object."""
    return getattr(value, "key", str(value))
