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

## Settings

Supported settings:

- `BIZCAL_DEFAULT_TIMEZONE`
- `BIZCAL_DEFAULT_COUNTRY`
- `BIZCAL_PRELOAD_YEARS`
- `BIZCAL_ENABLE_DB_MODELS`
- `BIZCAL_DEFAULT_CALENDAR_NAME`
- `BIZCAL_DEFAULT_CALENDAR`
- `BIZCAL_CALENDARS`

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

## Services

Import recommendation:

```python
from django_bizcal.django_api import get_calendar, set_calendar_day_override, set_calendar_holiday
```

The `django_api` module is the stable Django-specific import surface for services, persistence helpers, and the optional model/provider layer.

### `get_default_calendar()`

Builds and caches the default calendar from Django settings.

```python
from django_bizcal.services import get_default_calendar

calendar = get_default_calendar()
deadline = calendar.add_business_hours(start_dt, 8)
```

### `build_calendar(config)`

Build a calendar from a dict using Django defaults as fallback context.

### `get_calendar(name)`

Return a named configured calendar and cache it for process reuse.

```python
from django_bizcal.services import get_calendar

calendar = get_calendar("operations_latam")
deadline = calendar.add_business_hours(start_dt, 6)
```

### `CalendarHoliday`

Optional Django model for persisted full-day closures keyed by logical calendar name.

```python
from datetime import date

from django_bizcal.models import CalendarHoliday
from django_bizcal.services import set_calendar_holiday, sync_calendar_holidays

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

Cache behavior:

- `reset_calendar_cache()` clears all named calendar instances
- `reset_calendar_cache(name)` clears only one named calendar
- holiday mutation helpers invalidate only the affected logical calendar

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
- `get_calendar_day_override(calendar_name, day, include_inactive=False)`
- `set_calendar_day_override(calendar_name, day, windows, name="", is_active=True)`
- `activate_calendar_day_override(calendar_name, day, windows=None, name=None)`
- `deactivate_calendar_day_override(calendar_name, day)`
- `delete_calendar_day_override(calendar_name, day)`
- `sync_calendar_day_overrides(calendar_name, overrides)`

These helpers normalize windows before saving them and invalidate only the affected named calendar cache entry after each mutation.

Precedence rules:

- `CalendarHoliday` closes the whole day
- `CalendarDayOverride` replaces the whole day with explicit windows
- if both exist for the same logical calendar and date, the day override wins

### `list_configured_calendars()`

Return the configured logical calendar names from settings.

### `reset_calendar_cache()`

Useful in tests or reload scenarios after changing settings.

## Recommended application usage

- Keep calendar construction in a service layer.
- Reuse singleton-like calendars through `get_default_calendar()` and `get_calendar(name)`.
- Use `CalendarHoliday` for tenant or organization closed dates without recompiling calendar configs.
- Use `CalendarDayOverride` when a specific date needs reduced hours, split shifts, or a one-off intraday schedule.
- Pass aware datetimes from Django models or `django.utils.timezone.now()`.
