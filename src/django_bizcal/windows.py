"""Wall-clock time windows, schedule blocks, and operations."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import time, timedelta
from typing import Any, cast

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


_DAY = timedelta(days=1)
_MAX_END_OFFSET_DAYS = 1


@dataclass(frozen=True, slots=True, order=True)
class ScheduleBlock:
    """A local-time work block `[start, end)` that may end on a following day.

    `end_offset_days` is `0` for a plain intraday block and `1` for a block that
    crosses midnight, such as an overnight shift from `22:00` to `06:00`. Blocks are
    materialization specifications only: they never take part in the intraday window
    algebra, and cross-midnight handling lives in `BusinessInterval` instead.
    """

    start: time
    end: time
    end_offset_days: int = 0

    def __post_init__(self) -> None:
        start = self.start.replace(microsecond=0)
        end = self.end.replace(microsecond=0)
        offset = int(self.end_offset_days)
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)
        object.__setattr__(self, "end_offset_days", offset)
        if offset < 0 or offset > _MAX_END_OFFSET_DAYS:
            raise ValidationError(
                "ScheduleBlock end_offset_days must be 0 or 1, "
                f"got {offset!r}; blocks may not span more than one midnight."
            )
        if offset == 0:
            if start >= end:
                raise ValidationError("ScheduleBlock start must be earlier than end.")
        elif end > start:
            raise ValidationError(
                "ScheduleBlock with end_offset_days=1 must end at or before its start time "
                "on the following day, so that the block never exceeds 24 hours."
            )

    @classmethod
    def from_pair(cls, start: TimeInput, end: TimeInput, end_offset_days: int = 0) -> ScheduleBlock:
        """Build a block from time-like inputs and an optional end-day offset."""
        return cls(
            start=coerce_time(start),
            end=coerce_time(end),
            end_offset_days=end_offset_days,
        )

    @classmethod
    def from_spec(cls, value: ScheduleBlockInput) -> ScheduleBlock:
        """Build a block from a block, a `TimeWindow`, or a 2- or 3-element tuple."""
        if isinstance(value, ScheduleBlock):
            return value
        if isinstance(value, TimeWindow):
            return cls(start=value.start, end=value.end)
        spec = tuple(cast(Sequence[Any], value))
        if len(spec) == 2:
            return cls.from_pair(spec[0], spec[1])
        if len(spec) == 3:
            return cls.from_pair(spec[0], spec[1], int(spec[2]))
        raise ValidationError(
            "A schedule block spec must be a 2-element (start, end) or "
            "3-element (start, end, end_offset_days) sequence."
        )

    @property
    def spans_midnight(self) -> bool:
        """Return whether the block ends on a later calendar day than it starts."""
        return self.end_offset_days > 0

    def duration_hint(self) -> timedelta:
        """Return the nominal duration, ignoring DST.

        Only meant for validation and diagnostics: the real elapsed duration is
        computed on the materialized `BusinessInterval`.
        """
        return self._linear_end() - _time_to_delta(self.start)

    def as_time_window(self) -> TimeWindow:
        """Return the equivalent `TimeWindow` for an intraday block."""
        if self.spans_midnight:
            raise ValidationError(
                "A ScheduleBlock that crosses midnight cannot be expressed as a TimeWindow."
            )
        return TimeWindow(start=self.start, end=self.end)

    def _linear_end(self) -> timedelta:
        return _time_to_delta(self.end) + self.end_offset_days * _DAY


ScheduleBlockInput = (
    tuple[TimeInput, TimeInput] | tuple[TimeInput, TimeInput, int] | TimeWindow | ScheduleBlock
)


def build_schedule_blocks(items: Iterable[ScheduleBlockInput]) -> tuple[ScheduleBlock, ...]:
    """Build, order, and merge schedule blocks from specs.

    Blocks are merged only when the merged result is still representable as a single
    block of at most 24 hours. Anything left unmerged, including blocks that overlap
    across consecutive days, is merged later by `normalize_intervals` once the blocks
    are materialized into timezone-aware intervals.
    """
    ordered = sorted(ScheduleBlock.from_spec(item) for item in items)
    if not ordered:
        return ()
    merged: list[ScheduleBlock] = [ordered[0]]
    for current in ordered[1:]:
        combined = _merge_schedule_blocks(merged[-1], current)
        if combined is None:
            merged.append(current)
        else:
            merged[-1] = combined
    return tuple(merged)


def _merge_schedule_blocks(left: ScheduleBlock, right: ScheduleBlock) -> ScheduleBlock | None:
    """Merge two ordered blocks, or return None when they must stay separate."""
    left_start = _time_to_delta(left.start)
    right_start = _time_to_delta(right.start)
    left_end = left._linear_end()
    right_end = right._linear_end()
    if left_end < right_start:
        return None
    end = max(left_end, right_end)
    if end - left_start > _DAY:
        return None
    offset, remainder = divmod(end, _DAY)
    return ScheduleBlock(
        start=left.start,
        end=_delta_to_time(remainder),
        end_offset_days=int(offset),
    )


def _delta_to_time(value: timedelta) -> time:
    total_seconds = int(value.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return time(hour=hours, minute=minutes, second=seconds)


def _time_to_delta(value: time) -> timedelta:
    return timedelta(hours=value.hour, minutes=value.minute, seconds=value.second)

