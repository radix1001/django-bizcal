"""Timezone-aware business intervals."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, tzinfo

from .exceptions import ValidationError
from .types import ensure_aware


@dataclass(frozen=True, slots=True, order=True)
class BusinessInterval:
    """A half-open aware datetime interval `[start, end)`."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        start = ensure_aware(self.start, param_name="start")
        end = ensure_aware(self.end, param_name="end")
        if start >= end:
            raise ValidationError("BusinessInterval start must be earlier than end.")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)

    def contains(self, value: datetime) -> bool:
        """Return whether the interval contains the given aware datetime."""
        current = ensure_aware(value, param_name="value").astimezone(self.start.tzinfo)
        return self.start <= current < self.end

    def duration(self) -> timedelta:
        """Return the real elapsed duration for the interval."""
        return self.end.astimezone(UTC) - self.start.astimezone(UTC)

    def overlaps(self, other: BusinessInterval) -> bool:
        """Return whether two intervals overlap."""
        other_in_self_tz = other.to_timezone(_require_tzinfo(self.start))
        return self.start < other_in_self_tz.end and other_in_self_tz.start < self.end

    def touches(self, other: BusinessInterval) -> bool:
        """Return whether two intervals are adjacent or overlapping."""
        other_in_self_tz = other.to_timezone(_require_tzinfo(self.start))
        return self.end >= other_in_self_tz.start and other_in_self_tz.end >= self.start

    def merge(self, other: BusinessInterval) -> BusinessInterval:
        """Merge touching intervals after normalizing timezone."""
        other_in_self_tz = other.to_timezone(_require_tzinfo(self.start))
        if not self.touches(other_in_self_tz):
            raise ValidationError("Only overlapping or adjacent intervals can be merged.")
        return BusinessInterval(
            start=min(self.start, other_in_self_tz.start),
            end=max(self.end, other_in_self_tz.end),
        )

    def intersection(self, other: BusinessInterval) -> BusinessInterval | None:
        """Return the overlapping interval, if any."""
        other_in_self_tz = other.to_timezone(_require_tzinfo(self.start))
        start = max(self.start, other_in_self_tz.start)
        end = min(self.end, other_in_self_tz.end)
        if start >= end:
            return None
        return BusinessInterval(start=start, end=end)

    def subtract(self, other: BusinessInterval) -> tuple[BusinessInterval, ...]:
        """Subtract another interval from this one."""
        overlap = self.intersection(other)
        if overlap is None:
            return (self,)
        pieces: list[BusinessInterval] = []
        if self.start < overlap.start:
            pieces.append(BusinessInterval(self.start, overlap.start))
        if overlap.end < self.end:
            pieces.append(BusinessInterval(overlap.end, self.end))
        return tuple(pieces)

    def to_timezone(self, tzinfo: tzinfo) -> BusinessInterval:
        """Return the interval converted to another timezone."""
        return BusinessInterval(
            start=self.start.astimezone(tzinfo),
            end=self.end.astimezone(tzinfo),
        )


def normalize_intervals(intervals: Iterable[BusinessInterval]) -> tuple[BusinessInterval, ...]:
    """Sort and merge overlapping or adjacent intervals."""
    ordered = sorted(intervals)
    if not ordered:
        return ()
    merged: list[BusinessInterval] = [ordered[0]]
    for current in ordered[1:]:
        previous = merged[-1]
        if previous.touches(current):
            merged[-1] = previous.merge(current)
        else:
            merged.append(current)
    return tuple(merged)


def intersect_intervals(
    left: Sequence[BusinessInterval],
    right: Sequence[BusinessInterval],
) -> tuple[BusinessInterval, ...]:
    """Return normalized intersections between two interval collections."""
    intersections: list[BusinessInterval] = []
    for left_interval in normalize_intervals(left):
        for right_interval in normalize_intervals(right):
            overlap = left_interval.intersection(right_interval)
            if overlap is not None:
                intersections.append(overlap)
    return normalize_intervals(intersections)


def subtract_intervals(
    left: Sequence[BusinessInterval],
    right: Sequence[BusinessInterval],
) -> tuple[BusinessInterval, ...]:
    """Subtract one interval collection from another."""
    remaining = list(normalize_intervals(left))
    for blocker in normalize_intervals(right):
        next_remaining: list[BusinessInterval] = []
        for interval in remaining:
            next_remaining.extend(interval.subtract(blocker))
        remaining = next_remaining
    return normalize_intervals(remaining)


def _require_tzinfo(value: datetime) -> tzinfo:
    tz = value.tzinfo
    if tz is None:
        raise ValidationError("BusinessInterval requires timezone-aware datetimes.")
    return tz
