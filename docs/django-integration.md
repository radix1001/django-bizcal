# Django integration

## Reusable app

Install the package and add it to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...,
    "django_bizcal",
]
```

The app does not ship models in v1, so adding it is lightweight.

## Settings

Supported settings:

- `BIZCAL_DEFAULT_TIMEZONE`
- `BIZCAL_DEFAULT_COUNTRY`
- `BIZCAL_PRELOAD_YEARS`
- `BIZCAL_ENABLE_DB_MODELS`
- `BIZCAL_DEFAULT_CALENDAR`

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

Reserved for future optional persistence support. It is exposed now so projects can keep a stable settings namespace.

### `BIZCAL_DEFAULT_CALENDAR`

Optional serializable dictionary consumed by `CalendarBuilder.from_dict(...)`.

If omitted, django-bizcal builds a default Monday to Friday `09:00-18:00` working calendar using the configured timezone, country, and preload years.

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

### `reset_calendar_cache()`

Useful in tests or reload scenarios after changing settings.

## Recommended application usage

- Keep calendar construction in a service layer.
- Reuse singleton-like calendars through `get_default_calendar()` or your own cached service factories.
- Pass aware datetimes from Django models or `django.utils.timezone.now()`.

