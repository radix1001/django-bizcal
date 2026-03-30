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
- `iter_business_days(start, end, inclusive=True)`
- `list_business_days(start, end, inclusive=True)`
- `count_business_days(start, end, inclusive=True)`
- `next_business_day(day)`
- `previous_business_day(day)`
- `is_business_time(dt)`
- `opening_for_day(day, tz=None)`
- `closing_for_day(day, tz=None)`
- `next_opening_datetime(dt)`
- `previous_closing_datetime(dt)`
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
- `next_business_day(...)` and `previous_business_day(...)` are inclusive of the input day.
- `next_opening_datetime(...)` and `previous_closing_datetime(...)` return real schedule boundaries, even when the input lies outside business time.
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

### `CalendarBuilder.to_dict(...)`

Serializes supported calendars back into declarative configuration suitable for:

- Django settings
- cache payloads
- fixtures
- round-trip reconstruction with `CalendarBuilder.from_dict(...)`

Public configuration typing is also exported:

- `CalendarConfig`
- `WorkingCalendarConfig`
- `UnionCalendarConfig`
- `IntersectionCalendarConfig`
- `DifferenceCalendarConfig`
- `OverrideCalendarConfig`
