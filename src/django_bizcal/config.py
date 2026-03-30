"""Public configuration types for declarative calendar definitions."""

from __future__ import annotations

from typing import (
    Literal,
    NotRequired,
    TypeAlias,
    TypedDict,
)

TimePairConfig: TypeAlias = tuple[str, str]
WeeklyScheduleConfig: TypeAlias = dict[int | str, list[TimePairConfig]]
DayOverrideConfig: TypeAlias = dict[str, list[TimePairConfig] | None]


class WorkingCalendarConfig(TypedDict):
    """Declarative config for a working calendar."""

    type: Literal["working"]
    weekly_schedule: WeeklyScheduleConfig
    tz: NotRequired[str]
    country: NotRequired[str]
    subdivision: NotRequired[str]
    years: NotRequired[list[int]]
    observed: NotRequired[bool]
    extra_holidays: NotRequired[list[str]]
    custom_holidays: NotRequired[list[str]]
    day_overrides: NotRequired[DayOverrideConfig]
    name: NotRequired[str]


class UnionCalendarConfig(TypedDict):
    """Declarative config for a union calendar."""

    type: Literal["union"]
    children: list[CalendarConfig]
    tz: NotRequired[str]


class IntersectionCalendarConfig(TypedDict):
    """Declarative config for an intersection calendar."""

    type: Literal["intersection"]
    children: list[CalendarConfig]
    tz: NotRequired[str]


class DifferenceCalendarConfig(TypedDict):
    """Declarative config for a difference calendar."""

    type: Literal["difference"]
    tz: NotRequired[str]
    base: NotRequired[CalendarConfig]
    subtract: NotRequired[CalendarConfig]
    children: NotRequired[list[CalendarConfig]]


class OverrideCalendarConfig(TypedDict):
    """Declarative config for an override calendar."""

    type: Literal["override"]
    base: CalendarConfig
    overrides: DayOverrideConfig
    tz: NotRequired[str]


CalendarConfig: TypeAlias = (
    WorkingCalendarConfig
    | UnionCalendarConfig
    | IntersectionCalendarConfig
    | DifferenceCalendarConfig
    | OverrideCalendarConfig
)
