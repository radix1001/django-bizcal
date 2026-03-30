"""Composable calendar implementations."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime

from ..exceptions import ValidationError
from ..intervals import (
    BusinessInterval,
    intersect_intervals,
    normalize_intervals,
    subtract_intervals,
)
from ..types import DateInput, TimeInput, TzInput, coerce_date
from ..windows import TimeWindow, build_time_windows
from .base import BusinessCalendar

OverrideInput = Mapping[DateInput, Iterable[tuple[TimeInput, TimeInput] | TimeWindow] | None]


class _CompositeCalendar(BusinessCalendar):
    __slots__ = ("_children",)

    def __init__(self, children: Sequence[BusinessCalendar], *, tz: TzInput | None = None) -> None:
        if not children:
            raise ValidationError(
                f"{self.__class__.__name__} requires at least one child calendar."
            )
        super().__init__(tz or children[0].tz)
        self._children = tuple(children)

    @property
    def children(self) -> tuple[BusinessCalendar, ...]:
        """Ordered child calendars."""
        return self._children


class UnionCalendar(_CompositeCalendar):
    """Calendar open when any child calendar is open."""

    def _business_windows_for_day_local(self, day: date) -> tuple[BusinessInterval, ...]:
        intervals: list[BusinessInterval] = []
        for child in self.children:
            intervals.extend(child.business_windows_for_day(day, tz=self.tz))
        return normalize_intervals(intervals)


class IntersectionCalendar(_CompositeCalendar):
    """Calendar open only when all child calendars are open."""

    def _business_windows_for_day_local(self, day: date) -> tuple[BusinessInterval, ...]:
        remaining = self.children[0].business_windows_for_day(day, tz=self.tz)
        for child in self.children[1:]:
            remaining = intersect_intervals(
                remaining,
                child.business_windows_for_day(day, tz=self.tz),
            )
            if not remaining:
                break
        return remaining


class DifferenceCalendar(BusinessCalendar):
    """Calendar created by subtracting one calendar from another."""

    __slots__ = ("_base", "_subtract")

    def __init__(
        self,
        base: BusinessCalendar,
        subtract: BusinessCalendar,
        *,
        tz: TzInput | None = None,
    ) -> None:
        super().__init__(tz or base.tz)
        self._base = base
        self._subtract = subtract

    @property
    def base(self) -> BusinessCalendar:
        """Base calendar before subtraction."""
        return self._base

    @property
    def subtract(self) -> BusinessCalendar:
        """Calendar whose windows are removed from the base calendar."""
        return self._subtract

    def _business_windows_for_day_local(self, day: date) -> tuple[BusinessInterval, ...]:
        base_windows = self.base.business_windows_for_day(day, tz=self.tz)
        subtract_windows = self.subtract.business_windows_for_day(day, tz=self.tz)
        return subtract_intervals(base_windows, subtract_windows)


class OverrideCalendar(BusinessCalendar):
    """Calendar that replaces the base schedule on specific dates."""

    __slots__ = ("_base", "_overrides")

    def __init__(
        self,
        base: BusinessCalendar,
        overrides: OverrideInput,
        *,
        tz: TzInput | None = None,
    ) -> None:
        super().__init__(tz or base.tz)
        self._base = base
        self._overrides = _normalize_overrides(overrides)

    @property
    def base(self) -> BusinessCalendar:
        """Base calendar used when no override exists for a given day."""
        return self._base

    @property
    def overrides(self) -> Mapping[date, tuple[TimeWindow, ...]]:
        """Explicit day overrides rendered in the override calendar timezone."""
        return self._overrides

    def _business_windows_for_day_local(self, day: date) -> tuple[BusinessInterval, ...]:
        if day in self.overrides:
            return tuple(
                BusinessInterval(
                    start=datetime.combine(day, window.start, tzinfo=self.tz),
                    end=datetime.combine(day, window.end, tzinfo=self.tz),
                )
                for window in self.overrides[day]
            )
        return self.base.business_windows_for_day(day, tz=self.tz)


def _normalize_overrides(
    overrides: OverrideInput,
) -> dict[date, tuple[TimeWindow, ...]]:
    normalized: dict[date, tuple[TimeWindow, ...]] = {}
    for key, values in overrides.items():
        normalized[coerce_date(key)] = () if values is None else build_time_windows(values)
    return normalized
