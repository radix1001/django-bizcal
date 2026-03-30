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
Its persistence layer is intentionally small: one optional model for full-day holiday closures, not full calendar-definition storage.

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

Enables optional database-backed holiday closures for named Django calendars.

When enabled:

- `get_default_calendar()` applies persisted closures for `BIZCAL_DEFAULT_CALENDAR_NAME`
- `get_calendar(name)` applies persisted closures for that logical name
- persisted closures are implemented as full-day overrides on top of the configured calendar

Current scope:

- backed by the `CalendarHoliday` model
- applies to named calendars resolved through the Django service layer
- intended for organization, tenant, client, or team-specific closed dates

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

### `list_configured_calendars()`

Return the configured logical calendar names from settings.

### `reset_calendar_cache()`

Useful in tests or reload scenarios after changing settings.

## Recommended application usage

- Keep calendar construction in a service layer.
- Reuse singleton-like calendars through `get_default_calendar()` and `get_calendar(name)`.
- Use `CalendarHoliday` for tenant or organization closed dates without recompiling calendar configs.
- Pass aware datetimes from Django models or `django.utils.timezone.now()`.
