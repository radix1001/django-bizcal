# django-bizcal

[![PyPI version](https://img.shields.io/pypi/v/django-bizcal.svg)](https://pypi.org/project/django-bizcal/)
[![Python versions](https://img.shields.io/pypi/pyversions/django-bizcal.svg)](https://pypi.org/project/django-bizcal/)
[![CI](https://github.com/radix1001/django-bizcal/actions/workflows/ci.yml/badge.svg)](https://github.com/radix1001/django-bizcal/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/radix1001/django-bizcal/blob/main/LICENSE)

`django-bizcal` is a production-oriented Python library for Django projects that need composable business calendars with official holidays, custom holidays, intraday schedules, timezone-aware arithmetic, and reusable service integration.

It is designed for SLA clocks, operational workflows, due dates, approvals, support desks, tenant-specific calendars, and country-specific business hours.

## Highlights

- Pure domain core with no ORM coupling.
- Official holidays via [`holidays`](https://pypi.org/project/holidays/).
- Custom organization or tenant holidays in memory.
- Intraday schedules with multiple windows per weekday.
- Calendar composition with union, intersection, difference, and override.
- Explicit timezone support based on `zoneinfo`.
- Reusable Django app with namespaced settings and service helpers.
- Optional database-backed holiday closures and per-day schedule overrides for named Django calendars.
- Modern packaging with `pyproject.toml`, wheel/sdist builds, pytest, and GitHub Actions.

## Installation

```bash
pip install django-bizcal
```

For local development:

```bash
pip install -e ".[dev]"
```

## Quickstart

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from django_bizcal import UnionCalendar, WorkingCalendar

cl = WorkingCalendar.from_country(
    country="CL",
    years=[2026, 2027],
    tz="America/Santiago",
    weekly_schedule={
        0: [("09:00", "13:00"), ("14:00", "18:00")],
        1: [("09:00", "13:00"), ("14:00", "18:00")],
        2: [("09:00", "13:00"), ("14:00", "18:00")],
        3: [("09:00", "13:00"), ("14:00", "18:00")],
        4: [("09:00", "13:00"), ("14:00", "17:00")],
    },
    extra_holidays=["2026-12-24", "2026-12-31"],
)

mx = WorkingCalendar.from_country(
    country="MX",
    years=[2026, 2027],
    tz="America/Mexico_City",
    weekly_schedule={
        0: [("09:00", "18:00")],
        1: [("09:00", "18:00")],
        2: [("09:00", "18:00")],
        3: [("09:00", "18:00")],
        4: [("09:00", "18:00")],
    },
)

regional = UnionCalendar([cl, mx], tz="UTC")

start = datetime(2026, 1, 5, 15, 0, tzinfo=ZoneInfo("UTC"))
deadline = regional.add_business_hours(start, 10)
elapsed = regional.business_minutes_between(start, deadline)
```

## Django integration

Add the reusable app:

```python
INSTALLED_APPS = [
    ...,
    "django_bizcal",
]
```

Configure a default calendar:

```python
BIZCAL_DEFAULT_TIMEZONE = "America/Santiago"
BIZCAL_DEFAULT_COUNTRY = "CL"
BIZCAL_PRELOAD_YEARS = [2026, 2027]
BIZCAL_DEFAULT_CALENDAR = {
    "type": "working",
    "tz": "America/Santiago",
    "country": "CL",
    "years": [2026, 2027],
    "weekly_schedule": {
        "0": [["09:00", "13:00"], ["14:00", "18:00"]],
        "1": [["09:00", "13:00"], ["14:00", "18:00"]],
        "2": [["09:00", "13:00"], ["14:00", "18:00"]],
        "3": [["09:00", "13:00"], ["14:00", "18:00"]],
        "4": [["09:00", "13:00"], ["14:00", "17:00"]],
    },
    "extra_holidays": ["2026-12-24", "2026-12-31"],
}
```

Consume it from application code:

```python
from django_bizcal.services import get_default_calendar

calendar = get_default_calendar()
deadline = calendar.add_business_hours(ticket.created_at, 8)
```

For projects with more than one operational calendar, define a named registry:

```python
BIZCAL_DEFAULT_TIMEZONE = "UTC"
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

Use named calendars from application code:

```python
from django_bizcal.services import get_calendar, get_default_calendar

support = get_default_calendar()
regional_ops = get_calendar("operations_latam")
```

Persisted holiday closures and per-day overrides can be enabled for named Django calendars:

```python
BIZCAL_ENABLE_DB_MODELS = True

from datetime import date

from django_bizcal.django_api import (
    CalendarHoliday,
    set_calendar_day_override,
    set_calendar_holiday,
)

CalendarHoliday.objects.create(
    calendar_name="support",
    day=date(2026, 12, 24),
    name="Company shutdown",
)

set_calendar_holiday("support", date(2026, 12, 31), name="Year end close")
set_calendar_day_override(
    "support",
    date(2026, 12, 24),
    [("09:00", "13:00")],
    name="Christmas Eve half day",
)
```

Once enabled, `get_default_calendar()` and `get_calendar(name)` automatically apply persisted rows that match the logical calendar name:

- `CalendarHoliday` closes a full day
- `CalendarDayOverride` replaces the day with one or more explicit intraday windows

If both exist for the same day, the per-day override wins because it is more specific.
The service helpers also clear only the affected cached named calendar automatically after each change.

Preferred Django-specific imports:

```python
from django_bizcal.django_api import get_calendar, set_calendar_holiday
```

## Calendar builder

```python
from django_bizcal import CalendarBuilder

calendar = CalendarBuilder.from_dict(
    {
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
    }
)
```

The builder also supports serialization back to declarative config:

```python
from django_bizcal import CalendarBuilder

config = CalendarBuilder.to_dict(calendar)
restored = CalendarBuilder.from_dict(config)
```

## API ergonomics

Common day- and boundary-level helpers are part of the public API:

- `iter_business_days(...)`, `list_business_days(...)`, `count_business_days(...)`
- `next_business_day(...)`, `previous_business_day(...)`
- `opening_for_day(...)`, `closing_for_day(...)`
- `next_opening_datetime(...)`, `previous_closing_datetime(...)`

Typed declarative config helpers are also exported for IDE and static typing support:

- `CalendarConfig`
- `WorkingCalendarConfig`
- `UnionCalendarConfig`
- `IntersectionCalendarConfig`
- `DifferenceCalendarConfig`
- `OverrideCalendarConfig`

## Architecture

- The domain core lives in `src/django_bizcal` and stays framework-light.
- `WorkingCalendar` handles business schedules and holiday lookup.
- Composition calendars project child windows into a reference timezone.
- The Django layer wraps settings, AppConfig, service helpers, and optional persistence for named calendar closures and per-day overrides.
- The public core remains framework-light even though Django-specific models are now available behind the reusable app boundary.

See the full documentation in:

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/api.md`](docs/api.md)
- [`docs/django-integration.md`](docs/django-integration.md)
- [`docs/release.md`](docs/release.md)

## Compatibility

- Python 3.11+
- Django 4.2, 5.0, 5.1

## Limitations

- Official holiday lookup requires the relevant years to be preloaded.
- Wall-clock times are interpreted with `zoneinfo`; DST transitions affect real elapsed durations.
- The library persists named calendar closures and per-day overrides, but not full calendar definitions or arbitrary composition graphs.

## Release

```bash
python -m build
pytest
```

The recommended release path uses GitHub Actions plus PyPI Trusted Publishing. Publishing guidance is documented in [`docs/release.md`](docs/release.md).

## Support

If `django-bizcal` helps your team, consider sponsoring ongoing maintenance, documentation, and new features through GitHub Sponsors or by reaching out for support and implementation work.
