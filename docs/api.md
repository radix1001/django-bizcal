# API

## Core types

### `TimeWindow`

Represents a half-open local-time window.

```python
from django_bizcal import TimeWindow

window = TimeWindow.from_pair("09:00", "13:00")
```

Key behavior:

- Validates `start < end`
- Merges adjacent or overlapping windows through normalization helpers
- Supports `intersection(...)` and `subtract(...)`

### `BusinessInterval`

Represents a timezone-aware half-open datetime interval.

Useful when inspecting rendered windows from a calendar.

## Calendars

### `WorkingCalendar`

Primary calendar type backed by:

- a weekly schedule
- an optional holiday provider
- optional day overrides

```python
from django_bizcal import WorkingCalendar

calendar = WorkingCalendar(
    tz="America/Santiago",
    weekly_schedule={
        0: [("09:00", "13:00"), ("14:00", "18:00")],
        1: [("09:00", "13:00"), ("14:00", "18:00")],
        2: [("09:00", "13:00"), ("14:00", "18:00")],
        3: [("09:00", "13:00"), ("14:00", "18:00")],
        4: [("09:00", "13:00"), ("14:00", "17:00")],
    },
)
```

Use `WorkingCalendar.from_country(...)` to combine weekly schedules with official holidays from `holidays`.

### `UnionCalendar`

Combines multiple calendars and stays open whenever any child is open.

### `IntersectionCalendar`

Combines multiple calendars and stays open only where every child overlaps.

### `DifferenceCalendar`

Removes one calendar's intervals from a base calendar.

### `OverrideCalendar`

Substitutes the full schedule of specific dates while delegating the rest to a base calendar.

## Operations

All calendar implementations expose:

- `is_business_day(value)`
- `is_business_time(dt)`
- `next_business_datetime(dt)`
- `previous_business_datetime(dt)`
- `add_business_time(dt, delta)`
- `add_business_hours(dt, hours)`
- `add_business_minutes(dt, minutes)`
- `business_time_between(start, end)`
- `business_minutes_between(start, end)`
- `business_hours_between(start, end)`
- `business_windows_for_day(day, tz=None)`

Notes:

- Datetime operations require aware datetimes.
- `business_windows_for_day(...)` returns `BusinessInterval` values.
- `previous_business_datetime(...)` may return the closing boundary of the last open interval when the input is outside business time.

## Builder

### `CalendarBuilder.from_dict(...)`

Supported `type` values:

- `working`
- `union`
- `intersection`
- `difference`
- `override`

Working calendar keys:

- `tz`
- `country`
- `subdivision`
- `years`
- `weekly_schedule`
- `extra_holidays`
- `custom_holidays`
- `day_overrides`
- `observed`
- `name`

Composition keys:

- `union` and `intersection`: `children`
- `difference`: `base` and `subtract`, or `children` with exactly two items
- `override`: `base` and `overrides`

