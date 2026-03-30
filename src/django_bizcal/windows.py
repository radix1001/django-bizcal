"""Wall-clock time windows and operations."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import time, timedelta

from .exceptions import ValidationError
from .types import TimeInput, coerce_time


@dataclass(frozen=True, slots=True, order=True)
class TimeWindow:
    """A half-open local-time window `[start, end)`."""

    start: time
    end: time

    def __post_init__(self) -> None:
        start = self.start.replace(microsecond=0)
        end = self.end.replace(microsecond=0)
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        if start >= end:
            raise ValidationError("TimeWindow start must be earlier than end.")

    @classmethod
    def from_pair(cls, start: TimeInput, end: TimeInput) -> TimeWindow:
        """Build a window from time-like inputs."""
        return cls(start=coerce_time(start), end=coerce_time(end))

    def contains(self, value: time) -> bool:
        """Return whether the given time falls inside the window."""
        current = value.replace(microsecond=0)
        return self.start <= current < self.end

    def duration(self) -> timedelta:
        """Return the wall-clock duration of the window."""
        return _time_to_delta(self.end) - _time_to_delta(self.start)

    def overlaps(self, other: TimeWindow) -> bool:
        """Return whether the window overlaps another one."""
        return self.start < other.end and other.start < self.end

    def touches(self, other: TimeWindow) -> bool:
        """Return whether the window is adjacent or overlapping."""
        return self.end >= other.start and other.end >= self.start

    def merge(self, other: TimeWindow) -> TimeWindow:
        """Merge two touching windows."""
        if not self.touches(other):
            raise ValidationError("Only overlapping or adjacent windows can be merged.")
        return TimeWindow(start=min(self.start, other.start), end=max(self.end, other.end))

    def intersection(self, other: TimeWindow) -> TimeWindow | None:
        """Return the overlapping window, if any."""
        start = max(self.start, other.start)
        end = min(self.end, other.end)
        if start >= end:
            return None
        return TimeWindow(start=start, end=end)

    def subtract(self, other: TimeWindow) -> tuple[TimeWindow, ...]:
        """Subtract another window from this one."""
        overlap = self.intersection(other)
        if overlap is None:
            return (self,)
        segments: list[TimeWindow] = []
        if self.start < overlap.start:
            segments.append(TimeWindow(self.start, overlap.start))
        if overlap.end < self.end:
            segments.append(TimeWindow(overlap.end, self.end))
        return tuple(segments)


def normalize_time_windows(windows: Iterable[TimeWindow]) -> tuple[TimeWindow, ...]:
    """Sort and merge overlapping or adjacent time windows."""
    ordered = sorted(windows)
    if not ordered:
        return ()
    merged: list[TimeWindow] = [ordered[0]]
    for current in ordered[1:]:
        previous = merged[-1]
        if previous.touches(current):
            merged[-1] = previous.merge(current)
        else:
            merged.append(current)
    return tuple(merged)


def intersect_time_windows(
    left: Sequence[TimeWindow],
    right: Sequence[TimeWindow],
) -> tuple[TimeWindow, ...]:
    """Return normalized intersections between two window collections."""
    intersections: list[TimeWindow] = []
    for left_window in normalize_time_windows(left):
        for right_window in normalize_time_windows(right):
            overlap = left_window.intersection(right_window)
            if overlap is not None:
                intersections.append(overlap)
    return normalize_time_windows(intersections)


def subtract_time_windows(
    left: Sequence[TimeWindow],
    right: Sequence[TimeWindow],
) -> tuple[TimeWindow, ...]:
    """Subtract one normalized window set from another."""
    remaining = list(normalize_time_windows(left))
    for blocker in normalize_time_windows(right):
        next_remaining: list[TimeWindow] = []
        for window in remaining:
            next_remaining.extend(window.subtract(blocker))
        remaining = next_remaining
    return normalize_time_windows(remaining)


def build_time_windows(
    items: Iterable[tuple[TimeInput, TimeInput] | TimeWindow],
) -> tuple[TimeWindow, ...]:
    """Build and normalize windows from tuples or TimeWindow instances."""
    windows = [
        item if isinstance(item, TimeWindow) else TimeWindow.from_pair(item[0], item[1])
        for item in items
    ]
    return normalize_time_windows(windows)


def _time_to_delta(value: time) -> timedelta:
    return timedelta(hours=value.hour, minutes=value.minute, seconds=value.second)

