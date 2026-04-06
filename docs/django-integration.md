# Django integration

## Reusable app

Install the package and add it to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...,
    "django_bizcal",
]
```

The app remains lightweight.
Its persistence layer is intentionally small: optional models for full-day closures and per-day intraday overrides, not full calendar-definition storage.

Resolved Django settings are also cached process-locally for reuse. In tests or
reload scenarios that mutate settings dynamically, call `reset_calendar_cache()`
or `reset_deadline_policy_cache()` before re-resolving calendars or policies.

## Settings

Supported settings:

- `BIZCAL_DEFAULT_TIMEZONE`
- `BIZCAL_DEFAULT_COUNTRY`
- `BIZCAL_PRELOAD_YEARS`
- `BIZCAL_ENABLE_DB_MODELS`
- `BIZCAL_DEFAULT_CALENDAR_NAME`
- `BIZCAL_DEFAULT_CALENDAR`
- `BIZCAL_CALENDARS`
- `BIZCAL_CALENDAR_RESOLVER`
- `BIZCAL_DEADLINE_POLICIES`
- `BIZCAL_DEADLINE_POLICY_RESOLVER`

### `BIZCAL_DEFAULT_TIMEZONE`

Defaults to Django's `TIME_ZONE`, falling back to `UTC`.

### `BIZCAL_DEFAULT_COUNTRY`

Optional default country used by the builder and the default calendar.

### `BIZCAL_PRELOAD_YEARS`

Accepts:

- a positive integer
- an explicit iterable of years

If set to `3`, the integration resolves it to current year minus one through current year plus one.

### `BIZCAL_ENABLE_DB_MODELS`

Enables optional database-backed closures and day overrides for named Django calendars.

When enabled:

- `get_default_calendar()` applies persisted closures for `BIZCAL_DEFAULT_CALENDAR_NAME`
- `get_calendar(name)` applies persisted overrides for that logical name
- persisted rows are applied as substitution-based day overrides on top of the configured calendar

Current scope:

- backed by the `CalendarHoliday` model
- backed by the `CalendarDayOverride` and `CalendarDayOverrideWindow` models
- applies to named calendars resolved through the Django service layer
- intended for organization, tenant, client, or team-specific closed dates and special schedules

### `BIZCAL_DEFAULT_CALENDAR`

Optional serializable dictionary consumed by `CalendarBuilder.from_dict(...)`.

If omitted, django-bizcal builds a default Monday to Friday `09:00-18:00` working calendar using the configured timezone, country, and preload years.

### `BIZCAL_DEFAULT_CALENDAR_NAME`

Logical name used by `get_default_calendar()` when multiple calendars are configured.

Defaults to `default`.

### `BIZCAL_CALENDARS`

Optional mapping of logical calendar names to declarative calendar configs.

Example:

```python
BIZCAL_DEFAULT_CALENDAR_NAME = "support"
BIZCAL_CALENDARS = {
    "support": {
        "type": "working",
        "tz": "UTC",
        "weekly_schedule": {
            "0": [["09:00", "18:00"]],
            "1": [["09:00", "18:00"]],
            "2": [["09:00", "18:00"]],
            "3": [["09:00", "18:00"]],
            "4": [["09:00", "18:00"]],
        },
    },
    "operations_latam": {
        "type": "union",
        "tz": "UTC",
        "children": [
            {
                "type": "working",
                "country": "CL",
                "years": [2026, 2027],
                "tz": "America/Santiago",
                "weekly_schedule": {
                    "0": [["09:00", "18:00"]],
                    "1": [["09:00", "18:00"]],
                    "2": [["09:00", "18:00"]],
                    "3": [["09:00", "18:00"]],
                    "4": [["09:00", "18:00"]],
                },
            },
            {
                "type": "working",
                "country": "MX",
                "years": [2026, 2027],
                "tz": "America/Mexico_City",
                "weekly_schedule": {
                    "0": [["09:00", "18:00"]],
                    "1": [["09:00", "18:00"]],
                    "2": [["09:00", "18:00"]],
                    "3": [["09:00", "18:00"]],
                    "4": [["09:00", "18:00"]],
                },
            },
        ],
    },
}
```

Rules:

- If `BIZCAL_CALENDARS` is configured, `BIZCAL_DEFAULT_CALENDAR_NAME` must point to one of its entries unless `BIZCAL_DEFAULT_CALENDAR` is also configured explicitly.
- If `BIZCAL_DEFAULT_CALENDAR` and `BIZCAL_CALENDARS[BIZCAL_DEFAULT_CALENDAR_NAME]` both define the default calendar, django-bizcal raises a configuration error instead of guessing precedence.

### `BIZCAL_CALENDAR_RESOLVER`

Optional callable or dotted import path used by `resolve_calendar_for(...)` and `get_calendar_for(...)`.

The resolver receives:

- `context`: a plain mapping with tenant-, client-, or region-like keys
- `bizcal_settings`: the resolved `BizcalSettings` instance for the current process

The resolver may return:

- a configured logical calendar name
- a serializable calendar config mapping
- `CalendarResolution`

Example:

```python
from django_bizcal.django_api import CalendarResolution


def support_calendar_resolver(*, context, bizcal_settings):
    region = str(context["region"]).strip().lower()
    if region in {"cl", "mx"}:
        return f"support_{region}"
    tenant = str(context["tenant"]).strip().lower()
    return CalendarResolution.for_config(
        {
            "type": "working",
            "tz": "America/Santiago",
            "weekly_schedule": {
                "0": [["09:00", "18:00"]],
                "1": [["09:00", "18:00"]],
                "2": [["09:00", "18:00"]],
                "3": [["09:00", "18:00"]],
                "4": [["09:00", "18:00"]],
            },
        },
        name=f"tenant:{tenant}",
        cache_key=f"tenant:{tenant}:{region}",
    )


BIZCAL_CALENDAR_RESOLVER = support_calendar_resolver
```

Guidance:

- return a logical name when the calendar already exists in `BIZCAL_CALENDARS`
- return a config mapping for ad hoc per-context calendars
- return `CalendarResolution.for_config(..., name=..., cache_key=...)` when you want both persisted override support and contextual memoization

### `BIZCAL_DEADLINE_POLICIES`

Optional mapping of logical policy names to declarative deadline-policy configs.

Example:

```python
BIZCAL_DEADLINE_POLICIES = {
    "support_p1": {
        "type": "business_duration",
        "business_hours": 4,
    },
    "vendor_follow_up": {
        "type": "business_days",
        "business_days": 2,
        "at": "13:30",
        "include_start": True,
    },
    "support_cutoff": {
        "type": "cutoff",
        "cutoff": "15:00",
        "before": {"type": "close_of_business"},
        "after": {"type": "next_business_day", "at": "closing"},
    },
}
```

This enables a lightweight policy layer for recurring operational rules without forcing each Django app to hand-roll deadline logic.

### `BIZCAL_DEADLINE_POLICY_RESOLVER`

Optional callable or dotted import path used by `resolve_deadline_policy_for(...)`
and `get_deadline_policy_for(...)`.

The resolver receives:

- `context`: a plain mapping with tenant-, priority-, workflow-, or region-like keys
- `bizcal_settings`: the resolved `BizcalSettings` instance for the current process

The resolver may return:

- a configured logical deadline-policy name
- a serializable deadline-policy config mapping
- `DeadlinePolicyResolution`

Example:

```python
from django_bizcal.django_api import DeadlinePolicyResolution


def support_policy_resolver(*, context, bizcal_settings):
    priority = str(context["priority"]).strip().lower()
    if priority == "critical":
        return "support_p1"
    tenant = str(context["tenant"]).strip().lower()
    return DeadlinePolicyResolution.for_config(
        {"type": "same_business_day", "at": "closing"},
        name=f"tenant_policy:{tenant}:{priority}",
        cache_key=f"tenant_policy:{tenant}:{priority}",
    )


BIZCAL_DEADLINE_POLICY_RESOLVER = support_policy_resolver
```

Guidance:

- return a logical name when the deadline policy already exists in `BIZCAL_DEADLINE_POLICIES`
- return a config mapping for ad hoc per-context policies
- return `DeadlinePolicyResolution.for_config(..., name=..., cache_key=...)` when you want contextual memoization with targeted policy-cache invalidation

## Services

Import recommendation:

```python
from django_bizcal.django_api import get_calendar, set_calendar_day_override, set_calendar_holiday
```

The `django_api` module is the stable Django-specific import surface for services, persistence helpers, and the optional model/provider layer.

### `get_default_calendar()`

Builds and caches the default calendar from Django settings.

```python
from django_bizcal.django_api import get_default_calendar

calendar = get_default_calendar()
deadline = calendar.add_business_hours(start_dt, 8)
```

### `build_calendar(config)`

Build a calendar from a dict using Django defaults as fallback context.

### `get_calendar(name)`

Return a named configured calendar and cache it for process reuse.

```python
from django_bizcal.django_api import get_calendar

calendar = get_calendar("operations_latam")
deadline = calendar.add_business_hours(start_dt, 6)
```

### `resolve_calendar_for(context=None, **kwargs)`

Run the contextual resolver and return a normalized `CalendarResolution`.

```python
from django_bizcal.django_api import resolve_calendar_for

resolution = resolve_calendar_for(tenant="acme", region="cl")
```

### `get_calendar_for(context=None, **kwargs)`

Resolve and return a calendar for tenant-, client-, or region-specific context.

```python
from django_bizcal.django_api import get_calendar_for

regional_support = get_calendar_for(region="cl")
tenant_calendar = get_calendar_for(tenant="acme", region="cl")
```

Behavior:

- named resolutions reuse `get_calendar(name)` and its cache
- config-only resolutions build an ad hoc calendar each call unless a `cache_key` is provided
- config resolutions with `name` and `cache_key` participate in persisted holiday and day-override application when `BIZCAL_ENABLE_DB_MODELS=True`
- duplicate keys between the `context` mapping and `**kwargs` raise a validation error instead of silently overriding values

### `get_deadline_policy(name)`

Build and cache a named deadline policy from `BIZCAL_DEADLINE_POLICIES`.

### `resolve_deadline_policy_for(context=None, **kwargs)`

Run the contextual deadline-policy resolver and return a normalized
`DeadlinePolicyResolution`.

```python
from django_bizcal.django_api import resolve_deadline_policy_for

resolution = resolve_deadline_policy_for(tenant="acme", priority="critical")
```

### `get_deadline_policy_for(context=None, **kwargs)`

Resolve and return a deadline policy for tenant-, priority-, workflow-, or region-specific context.

```python
from django_bizcal.django_api import get_deadline_policy_for

policy = get_deadline_policy_for(tenant="acme", priority="critical")
```

Behavior:

- named resolutions reuse `get_deadline_policy(name)` and its cache
- config-only resolutions build an ad hoc policy each call unless a `cache_key` is provided
- config resolutions with `name` and `cache_key` participate in targeted policy-cache invalidation
- duplicate keys between the `context` mapping and `**kwargs` raise a validation error instead of silently overriding values

### `get_deadline_policy_config(name)` and `build_deadline_policy(config)`

Use these helpers when you need:

- the raw declarative policy config from settings
- to build an ad hoc policy object from a mapping before resolving it manually

### `compute_deadline(policy_name, start, ...)`

Compute a `BusinessDeadline` from a named policy using either:

- an explicit `calendar=...`
- contextual resolver inputs such as `tenant=...`, `region=...`
- or the default configured calendar when neither is provided

```python
from django_bizcal.django_api import compute_deadline

deadline = compute_deadline(
    "support_cutoff",
    ticket.created_at,
    tenant=ticket.tenant,
    region=ticket.region,
)
```

Rules:

- explicit `calendar=...` and contextual resolver inputs cannot be mixed in the same call
- the resolved calendar's logical `calendar_name` is propagated automatically into the resulting `BusinessDeadline`
- named deadline policies are cached similarly to named calendars
- passing `policy_name=None` uses `BIZCAL_DEADLINE_POLICY_RESOLVER` with the same contextual inputs used for calendar resolution

### Deadline helpers with Django services

The deadline helpers are part of the stable public API and work naturally with `get_default_calendar()`, `get_calendar(name)`, and `get_calendar_for(...)`.

```python
from datetime import timedelta

from django_bizcal.django_api import deadline_for, get_calendar_for, now

calendar = get_calendar_for(tenant="acme", region="cl")
deadline = deadline_for(now(), timedelta(hours=8), calendar=calendar)
```

Because deadline helpers are also available as `BusinessCalendar` instance methods, this is often the cleanest style in Django code:

```python
calendar = get_calendar_for(tenant="acme", region="cl")
deadline = calendar.deadline_for(now(), timedelta(hours=8))
```

For calendars obtained through `get_default_calendar()`, `get_calendar(name)`, and `get_calendar_for(...)`, django-bizcal also attaches the logical `calendar_name` to the calendar instance. As a result, `deadline.calendar_name` is preserved automatically when you call `calendar.deadline_for(...)`.

A realistic helpdesk flow looks like this:

```python
from datetime import timedelta

from django_bizcal.django_api import get_calendar_for

calendar = get_calendar_for(tenant=ticket.tenant, region=ticket.region)
deadline = calendar.deadline_for(ticket.created_at, timedelta(hours=8))
```

See `examples/helpdesk_sla.py` for a fuller example including remaining time and breach checks.

You can also resolve date-based due times directly:

```python
from django_bizcal.django_api import business_deadline_at_close, due_on_next_business_day

next_open = due_on_next_business_day("2026-03-06", calendar=calendar)
month_end_cutoff = business_deadline_at_close(
    "2026-03-05",
    2,
    calendar=calendar,
)
```

For teams that prefer declarative rules over direct helper composition, use named deadline policies instead:

```python
from django_bizcal.django_api import compute_deadline

deadline = compute_deadline(
    "support_cutoff",
    ticket.created_at,
    tenant=ticket.tenant,
    region=ticket.region,
)
```

Or let both the calendar and the deadline policy come from shared business context:

```python
from django_bizcal.django_api import compute_deadline

deadline = compute_deadline(
    policy_name=None,
    start=ticket.created_at,
    tenant=ticket.tenant,
    region=ticket.region,
    priority=ticket.priority,
)
```

Or use a policy directly from a resolved calendar:

```python
deadline = calendar.resolve_deadline_policy_dict(
    ticket.created_at,
    {
        "type": "business_days",
        "business_days": 2,
        "at": "13:30",
        "include_start": True,
    },
)
```

### `CalendarHoliday`

Optional Django model for persisted full-day closures keyed by logical calendar name.

```python
from datetime import date

from django_bizcal.django_api import CalendarHoliday, set_calendar_holiday, sync_calendar_holidays

CalendarHoliday.objects.create(
    calendar_name="support",
    day=date(2026, 12, 24),
    name="Company shutdown",
)

set_calendar_holiday("support", date(2026, 12, 31), name="Year end close")
sync_calendar_holidays("support", [date(2026, 12, 24), date(2026, 12, 31)])
```

Fields:

- `calendar_name`
- `day`
- `name`
- `is_active`

The uniqueness constraint is `(calendar_name, day)`.

### Calendar holiday helpers

The Django service layer also exposes convenience helpers that invalidate the cached named calendars automatically after each mutation:

- `list_calendar_holidays(calendar_name, include_inactive=False)`
- `get_calendar_holiday(calendar_name, day, include_inactive=False)`
- `set_calendar_holiday(calendar_name, day, name="", is_active=True)`
- `activate_calendar_holiday(calendar_name, day, name=None)`
- `deactivate_calendar_holiday(calendar_name, day)`
- `delete_calendar_holiday(calendar_name, day)`
- `sync_calendar_holidays(calendar_name, days)`

These helpers are the recommended way to manage `CalendarHoliday` rows from application code because they keep `get_calendar(name)` and `get_default_calendar()` coherent without requiring a manual `reset_calendar_cache()`.

For read-only inspection without touching ORM relations directly, you can also use:

- `list_calendar_holiday_days(calendar_name, include_inactive=False)`

Cache behavior:

- `reset_calendar_cache()` clears all named calendar instances
- `reset_calendar_cache()` also clears all named and contextual deadline-policy caches
- `reset_calendar_cache(name)` clears only one named calendar
- holiday mutation helpers invalidate only the affected logical calendar
- contextual cached calendars whose `CalendarResolution.name` matches the invalidated logical name are also evicted
- admin saves and deletes also invalidate the affected logical calendar
- direct ORM saves and deletes invalidate the affected logical calendar after transaction commit
- the Django admin exposes bulk activate/deactivate actions for holiday rows

### `CalendarDayOverride`

Optional Django model for persisted per-day schedule replacement keyed by logical calendar name.

```python
from datetime import date

from django_bizcal.django_api import set_calendar_day_override

set_calendar_day_override(
    "support",
    date(2026, 12, 24),
    [("09:00", "13:00"), ("14:00", "16:00")],
    name="Christmas Eve reduced hours",
)
```

`CalendarDayOverrideWindow` stores the ordered intraday windows that belong to a given override.
The uniqueness constraint on `CalendarDayOverride` is `(calendar_name, day)`, and window positions are unique per override.

### Calendar day override helpers

The Django service layer also exposes convenience helpers for persisted intraday schedule replacements:

- `list_calendar_day_overrides(calendar_name, include_inactive=False)`
- `list_calendar_day_override_windows(calendar_name, include_inactive=False)`
- `get_calendar_day_override(calendar_name, day, include_inactive=False)`
- `get_calendar_day_override_windows(calendar_name, day, include_inactive=False)`
- `set_calendar_day_override(calendar_name, day, windows, name="", is_active=True)`
- `activate_calendar_day_override(calendar_name, day, windows=None, name=None)`
- `deactivate_calendar_day_override(calendar_name, day)`
- `delete_calendar_day_override(calendar_name, day)`
- `sync_calendar_day_overrides(calendar_name, overrides)`

These helpers normalize windows before saving them and invalidate only the affected named calendar cache entry after each mutation.
The `*_windows(...)` helpers return normalized `TimeWindow` tuples so application code can inspect persisted schedules without traversing ORM relations.

Precedence rules:

- `CalendarHoliday` closes the whole day
- `CalendarDayOverride` replaces the whole day with explicit windows
- if both exist for the same logical calendar and date, the day override wins

Operational behavior:

- admin inline edits for `CalendarDayOverrideWindow` rows are normalized after save
- adjacent or overlapping persisted windows are compacted into normalized windows
- direct ORM saves and deletes on override models also invalidate the affected named calendar after transaction commit
- the Django admin exposes a window summary column plus bulk activate/deactivate actions for day overrides
- contextual cached calendars keyed with the same logical `name` are also invalidated

### `list_configured_calendars()`

Return the configured logical calendar names from settings.

### `reset_calendar_cache()`

Useful in tests or reload scenarios after changing settings.

### `reset_deadline_policy_cache()`

Useful in tests or reload scenarios after changing deadline-policy settings or contextual resolver behavior.

## Recommended application usage

- Keep calendar construction in a service layer.
- Reuse singleton-like calendars through `get_default_calendar()`, `get_calendar(name)`, and `get_calendar_for(...)` when contextual memoization is configured.
- Reuse `get_deadline_policy(name)` and `get_deadline_policy_for(...)` instead of rebuilding policy objects repeatedly.
- Use `CalendarHoliday` for tenant or organization closed dates without recompiling calendar configs.
- Use `CalendarDayOverride` when a specific date needs reduced hours, split shifts, or a one-off intraday schedule.
- Keep resolver logic thin: derive the logical name or config from business context, then let django-bizcal handle caching and persisted overrides.
- Prefer shared context keys between calendar and deadline-policy resolvers so `compute_deadline(policy_name=None, ...)` can resolve both layers consistently.
- Pass aware datetimes from Django models or `django.utils.timezone.now()`.
