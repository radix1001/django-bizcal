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

### `ScheduleBlock`

Represents a local-time work block that may end on a following day, so an overnight
shift can be expressed as a single block.

```python
from django_bizcal import ScheduleBlock, build_schedule_blocks

night = ScheduleBlock.from_pair("22:00", "06:00", 1)
blocks = build_schedule_blocks([("09:00", "18:00"), ("22:00", "06:00", 1)])
```

Key behavior:

- `end_offset_days` is `0` for an intraday block and `1` for a block that crosses midnight
- With `end_offset_days=0` it validates `start < end`, exactly like `TimeWindow`
- With `end_offset_days=1` it validates `end <= start`, which bounds a block to 24 hours
- Any other offset is rejected: a block may never span more than one midnight
- `build_schedule_blocks(...)` orders and merges blocks; blocks that cannot merge into a
  single 24-hour block are left alone and merged later as timezone-aware intervals
- Blocks are materialization specifications only: they deliberately have no
  `overlaps` / `merge` / `intersection` / `subtract`, because cross-midnight arithmetic
  belongs to `BusinessInterval`

Schedule specs accept a `TimeWindow`, a `ScheduleBlock`, a `(start, end)` pair, or a
`(start, end, end_offset_days)` triple, everywhere a weekly schedule or a day override
is configured.

### `BusinessInterval`

Represents a timezone-aware half-open datetime interval.

Useful when inspecting rendered windows from a calendar.

## Exceptions

Stable package-level exception types:

- `BizcalError`
- `ValidationError`
- `CalendarConfigurationError`
- `CalendarRangeError`
- `TimezoneError`

Guidance:

- catch `BizcalError` when you want a single library-level boundary
- catch `ValidationError` for structurally invalid user or config input
- catch `CalendarConfigurationError` for invalid calendar, resolver, or settings configuration
- catch `CalendarRangeError` when the requested search horizon cannot be satisfied

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

Overnight shifts are configured with a third element on the schedule spec:

```python
night_shift = WorkingCalendar(
    tz="America/Santiago",
    weekly_schedule={weekday: [("22:00", "06:00", 1)] for weekday in range(5)},
)
```

`WorkingCalendar` adds two members for overnight work:

- `business_blocks_for_day(day)` returns whole blocks anchored to the day on which they
  start, without clipping them at midnight, so the Monday query reports the shift ending
  at `06:00` on Tuesday. Only `WorkingCalendar` exposes it: a composite calendar receives
  coverage from its children already clipped to civil days and could not reconstruct the
  identity of the original block.
- `holiday_truncates_overnight` (default `False`) decides what a closed day does to the
  previous night's block. With the default, a holiday or a closing day override suppresses
  only the blocks that *start* that day, and the incoming tail survives. Set it to `True`
  to suppress every bit of coverage on a closed day, truncating the incoming block at
  midnight. A weekday that simply has no scheduled block is not "closed" in this sense and
  always receives the tail.

### `UnionCalendar`

Combines multiple calendars and stays open whenever any child is open.

### `IntersectionCalendar`

Combines multiple calendars and stays open only where every child overlaps.

### `DifferenceCalendar`

Removes one calendar's intervals from a base calendar.

### `OverrideCalendar`

Substitutes the full schedule of specific dates while delegating the rest to a base calendar.

An override replaces the whole civil day, including the tail of an overnight block the base
calendar started the previous day. Because `apply_database_overrides(...)` builds an
`OverrideCalendar`, a persisted holiday truncates an incoming overnight block at midnight
regardless of the base calendar's `holiday_truncates_overnight` setting. Use a
`WorkingCalendar` day override when that tail has to survive.

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
- `business_windows_for_day(...)` returns `BusinessInterval` values clipped to the civil day.
  Adjacent days tile the timeline exactly, so an overnight shift is reported as
  `[22:00, 24:00)` on its starting day and `[00:00, 06:00)` on the next one, with no gap.
- `business_windows_for_range(...)` is not clipped per day: it merges an overnight block
  into a single interval.
- `is_business_day(...)` is `True` for a day covered only by the tail of an overnight block.
- `next_business_day(...)` and `previous_business_day(...)` are inclusive of the input day.
- `next_opening_datetime(...)` and `previous_closing_datetime(...)` return real schedule boundaries, even when the input lies outside business time. Their boundaries are civil-day boundaries: while an overnight block is open across midnight, they report midnight rather than the block's own start or end.
- Deadlines resolved `at="closing"` do follow an overnight block past midnight on a
  `WorkingCalendar`; on a composite calendar the closing of an overnight block is midnight.
- `previous_business_datetime(...)` may return the closing boundary of the last open interval when the input is outside business time.

## Deadlines

### `BusinessDeadline`

Represents a computed deadline tied to a concrete `BusinessCalendar`.

Fields:

- `start`
- `service_time`
- `deadline`
- `calendar`
- `calendar_name`

Helpers:

- `remaining(at=None)`
- `remaining_minutes(at=None)`
- `remaining_hours(at=None)`
- `is_breached(at=None)`

### Deadline functions

- `deadline_for(start, service_time, calendar=...)`
- `breach_at(start, service_time, calendar=...)`
- `remaining_business_time(deadline, calendar=None, now=None)`
- `is_breached(deadline, calendar=None, now=None)`
- `due_on_next_business_day(day, calendar=..., at="opening"|"closing"|time, tz=None)`
- `business_deadline_at_close(start_day, business_days, calendar=..., include_start=False, tz=None)`

Semantics:

- `service_time` is expressed as real elapsed business time through `timedelta`
- `remaining_business_time(...)` is signed: positive before the deadline, negative after breach
- `due_on_next_business_day(...)` always resolves strictly after the input day
- when `at` is a wall-clock time between windows, the helper snaps forward to the next interval start on that same business day
- when `at` is later than the last open interval, the helper clamps to that day's closing boundary

Every `BusinessCalendar` also exposes bound convenience methods:

- `calendar.deadline_for(start, service_time, calendar_name=None)`
- `calendar.breach_at(start, service_time)`
- `calendar.due_on_next_business_day(day, at="opening"|"closing"|time, tz=None)`
- `calendar.business_deadline_at_close(start_day, business_days, include_start=False, tz=None)`

When a calendar comes from Django service resolution, `calendar.calendar_name` is populated with the logical configured or contextual name, and `calendar.deadline_for(...)` propagates that value into `BusinessDeadline.calendar_name` automatically.

## Deadline policies

The policy layer provides reusable, declarative deadline rules on top of the calendar engine.

Built-in policy types:

- `BusinessDurationPolicy`
- `CloseOfBusinessPolicy`
- `BusinessDaysPolicy`
- `SameBusinessDayPolicy`
- `NextBusinessDayPolicy`
- `BusinessDaysAtClosePolicy`
- `CutoffPolicy`

All policies implement the `DeadlinePolicy` protocol:

- `resolve(start, calendar=..., calendar_name=None) -> BusinessDeadline`

### `BusinessDurationPolicy`

Adds a business-time duration to the starting datetime.

### `CloseOfBusinessPolicy`

Resolves to the current business day's closing boundary, rolling forward when the input is already past close or the day is not business-open.

### `NextBusinessDayPolicy`

Resolves to a boundary on the next business day:

- `at="opening"`
- `at="closing"`
- `at="HH:MM"` with forward snapping inside the day

### `BusinessDaysPolicy`

Resolves after a number of business-day boundaries using:

- `at="opening"`
- `at="closing"`
- `at="HH:MM"` with forward snapping inside the day

Parameters:

- `business_days`
- `at`
- `include_start`
- `tz`

### `BusinessDaysAtClosePolicy`

Compatibility convenience policy that resolves after a number of business-day
closing boundaries.

Parameters:

- `business_days`
- `include_start`
- `tz`

### `CutoffPolicy`

Dispatches to `before` or `after` depending on the local wall-clock time of the input datetime.

Example:

```python
from django_bizcal import DeadlinePolicyBuilder

policy = DeadlinePolicyBuilder.from_dict(
    {
        "type": "cutoff",
        "cutoff": "15:00",
        "before": {"type": "close_of_business"},
        "after": {"type": "next_business_day", "at": "closing"},
    }
)
```

### `DeadlinePolicyBuilder.from_dict(...)`

Supported `type` values:

- `business_duration`
- `close_of_business`
- `business_days`
- `same_business_day`
- `next_business_day`
- `business_days_at_close`
- `cutoff`

Public policy configuration typing is also exported:

- `DeadlinePolicyConfig`
- `BusinessDurationPolicyConfig`
- `CloseOfBusinessPolicyConfig`
- `BusinessDaysPolicyConfig`
- `SameBusinessDayPolicyConfig`
- `NextBusinessDayPolicyConfig`
- `BusinessDaysAtClosePolicyConfig`
- `CutoffPolicyConfig`

### `DeadlinePolicyBuilder.to_dict(...)`

Serializes supported policy objects back into normalized declarative config suitable for:

- Django settings
- cache payloads
- fixtures
- round-trip reconstruction with `DeadlinePolicyBuilder.from_dict(...)`

Every `BusinessCalendar` also exposes bound policy helpers:

- `calendar.resolve_deadline_policy(start, policy, calendar_name=None)`
- `calendar.resolve_deadline_policy_dict(start, policy_config, calendar_name=None)`

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
- `holiday_truncates_overnight`

Schedule entries in `weekly_schedule` and `day_overrides` are `[start, end]` pairs, or
`[start, end, end_offset_days]` triples for a block that ends on the following day.
`to_dict(...)` emits the triple form only for blocks that actually cross midnight, so a
calendar without overnight blocks serializes exactly as it did before the feature existed.

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

## Django-specific API

The root package intentionally stays framework-light.
For Django-only persistence and service helpers, use `django_bizcal.django_api`.

Stable Django-specific exports include:

- `CalendarResolution`
- `DeadlinePolicyResolution`
- `CalendarHoliday`
- `CalendarDayOverride`
- `CalendarDayOverrideWindow`
- `DatabaseDayOverrideProvider`
- `DatabaseHolidayProvider`
- `apply_database_holiday_overrides(...)`
- `apply_database_overrides(...)`
- `get_default_calendar()`
- `get_calendar(name)`
- `get_deadline_policy_config(name)`
- `get_deadline_policy(name)`
- `resolve_deadline_policy_for(context=None, **kwargs)`
- `get_deadline_policy_for(context=None, **kwargs)`
- `build_deadline_policy(config)`
- `compute_deadline(policy_name, start, calendar=None, context=None, calendar_name=None, **kwargs)`
- `resolve_calendar_for(context=None, **kwargs)`
- `get_calendar_for(context=None, **kwargs)`
- `list_configured_calendars()`
- `list_configured_deadline_policies()`
- `list_calendar_holidays(...)`
- `list_calendar_holiday_days(...)`
- `list_calendar_day_overrides(...)`
- `list_calendar_day_override_windows(...)`
- `get_calendar_holiday(...)`
- `get_calendar_day_override(...)`
- `get_calendar_day_override_windows(...)`
- `set_calendar_holiday(...)`
- `set_calendar_day_override(...)`
- `activate_calendar_holiday(...)`
- `activate_calendar_day_override(...)`
- `deactivate_calendar_holiday(...)`
- `deactivate_calendar_day_override(...)`
- `delete_calendar_holiday(...)`
- `delete_calendar_day_override(...)`
- `sync_calendar_holidays(...)`
- `sync_calendar_day_overrides(...)`
- `reset_calendar_cache(name=None)`
- `reset_deadline_policy_cache(name=None)`

### Context-aware resolution

`resolve_calendar_for(...)` delegates to `BIZCAL_CALENDAR_RESOLVER` and normalizes the result into `CalendarResolution`.

Supported resolver outputs:

- a named calendar such as `"support_cl"`
- a serializable `CalendarConfig`
- `CalendarResolution`

`CalendarResolution` fields:

- `name`: logical calendar name, also used for persisted override lookup when DB models are enabled
- `config`: explicit calendar definition to build instead of looking up a named config from settings
- `cache_key`: optional memoization key for config-based contextual calendars

`get_calendar_for(...)` resolves the context and returns a built calendar:

- named resolutions reuse the existing named calendar cache
- config-only resolutions build an ad hoc calendar each call unless `cache_key` is provided
- config resolutions with both `name` and `cache_key` can also participate in persisted holiday and day-override application plus targeted cache invalidation

### Context-aware deadline-policy resolution

`resolve_deadline_policy_for(...)` delegates to `BIZCAL_DEADLINE_POLICY_RESOLVER`
and normalizes the result into `DeadlinePolicyResolution`.

Supported resolver outputs:

- a named deadline policy such as `"support_p1"`
- a serializable `DeadlinePolicyConfig`
- `DeadlinePolicyResolution`

`DeadlinePolicyResolution` fields:

- `name`: logical deadline-policy name
- `config`: explicit deadline-policy definition to build instead of looking up a named config from settings
- `cache_key`: optional memoization key for config-based contextual deadline policies

`get_deadline_policy_for(...)` resolves the context and returns a built policy:

- named resolutions reuse the existing named deadline-policy cache
- config-only resolutions build an ad hoc policy each call unless `cache_key` is provided
- config resolutions with both `name` and `cache_key` participate in targeted deadline-policy cache invalidation

`compute_deadline(...)` keeps the existing named-policy path, and also accepts
`policy_name=None` to resolve the deadline policy from the same contextual inputs
used for calendar resolution.
