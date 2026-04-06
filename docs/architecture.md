# Architecture

## Product and package naming

- Distribution name: `django-bizcal`
- Import name: `django_bizcal`

The distribution name is explicit for PyPI and keeps strong discoverability in Django ecosystems. The import name follows normal Python packaging conventions.

## Architectural goals

- Keep the business-time engine reusable outside Django.
- Make Django integration ergonomic instead of invasive.
- Keep the v1 public API compact, explicit, and semver-friendly.
- Support real calendar composition instead of only simple business-day checks.
- Prefer serializable configuration so projects can define calendars declaratively.

## Layering

### Pure domain

Modules:

- `windows.py`
- `intervals.py`
- `providers.py`
- `calendars/base.py`
- `calendars/working.py`
- `calendars/composite.py`
- `builder.py`
- `deadlines.py`
- `policies.py`

Responsibilities:

- Model wall-clock windows and timezone-aware intervals.
- Normalize, merge, intersect, and subtract time windows.
- Represent working calendars and composed calendars.
- Compute business-time arithmetic and elapsed business time.
- Provide small application-oriented helpers for SLA clocks and due-date calculation without coupling the core to Django.
- Provide a declarative policy layer for reusable cutoff and due-date rules without pushing workflow logic into Django settings or ORM models.

### Holiday providers

Providers are isolated behind `HolidayProvider`.

Included in v1:

- `HolidaysProvider` for official holidays via `holidays`
- `SetHolidayProvider` for custom in-memory dates
- `CompositeHolidayProvider` to combine both

Included in the Django layer:

- `DatabaseHolidayProvider` for persisted holiday dates via Django ORM
- `DatabaseDayOverrideProvider` for persisted intraday day overrides via Django ORM

This keeps future database-backed providers additive rather than invasive.

### Django integration

Modules:

- `apps.py`
- `settings.py`
- `services.py`
- `resolvers.py`
- `models.py`
- `db.py`

Responsibilities:

- Expose a reusable `AppConfig`
- Resolve namespaced settings
- Cache resolved settings for process-local reuse
- Build and cache the default calendar
- Resolve named calendars and optionally apply persisted holiday closures and day overrides
- Resolve calendars from tenant-, client-, or region-like context through a pluggable resolver hook
- Resolve deadline policies from tenant-, priority-, or workflow-like context through a pluggable resolver hook
- Provide helpers that fit typical Django service usage

No domain logic depends on ORM models, request objects, middleware, or settings globals.

## Performance strategy

The core calendar objects are treated as immutable once built.

That lets the domain layer memoize normalized business windows per local day on
each calendar instance, while keeping the cache bounded so long-lived processes
do not grow without limit.

The practical effect is:

- repeated day queries on the same calendar instance avoid rebuilding intervals
- range and business-time operations reuse previously computed day windows
- Django invalidation still happens by replacing cached calendar instances rather than mutating them in place

## Why persistence stays minimal

The hardest part of this product is correct business-time behavior across holidays, schedules, composition, and timezones. Full calendar-definition persistence would force an early schema and serialization contract before the core API settles.

The chosen strategy is:

- Stabilize the pure domain first.
- Make calendars declarative through `CalendarBuilder.from_dict(...)`.
- Add only the smallest persistence units with immediate value:
  - persisted holiday closures keyed by logical calendar name
  - persisted per-day override windows keyed by logical calendar name and date
- Keep contextual calendar selection in application code through `BIZCAL_CALENDAR_RESOLVER` instead of persisting full calendar graphs prematurely
- Keep weekly schedules and composition declarative rather than ORM-managed for now.

This keeps the library lighter, easier to test, and easier to embed into other Django codebases while still unlocking tenant- or client-specific closed dates and one-off special schedules.

## Timezone strategy

- Every calendar has a reference timezone.
- Working schedules are defined as local wall-clock times in that timezone.
- Business operations accept aware datetimes.
- Composed calendars project child intervals into their own reference timezone before merging.
- `zoneinfo` is the only timezone implementation used by the library.

DST rationale:

- Schedules stay human-friendly as wall-clock windows.
- Real elapsed business time is computed from aware datetimes, so DST can shorten or lengthen a business interval.

## Holiday year policy

Official holidays are not queried lazily without bounds. Instead, years are explicit.

Rationale:

- `holidays` can generate data efficiently when the time horizon is known.
- Explicit year sets make failures visible when a project moves outside its configured horizon.
- Django settings expose `BIZCAL_PRELOAD_YEARS` to centralize that policy.

Default Django policy:

- `BIZCAL_PRELOAD_YEARS = 3`
- Interpreted as current year minus one through current year plus one

## Composition semantics

- `UnionCalendar`: open if any child is open
- `IntersectionCalendar`: open only where all children overlap
- `DifferenceCalendar`: subtract one calendar's windows from another
- `OverrideCalendar`: replace the base calendar on specific dates

Overrides are intentionally substitution-based rather than patch-based. A date override replaces the entire day's schedule. This keeps the model easy to reason about and avoids subtle precedence bugs.

The same rule applies in Django persistence:

- `CalendarHoliday` models a closed day
- `CalendarDayOverride` plus `CalendarDayOverrideWindow` models an explicit replacement schedule
- persisted day overrides take precedence over persisted holiday closures for the same logical calendar and date

## Public API strategy

Stable v1 public imports are exposed from `django_bizcal`:

- `TimeWindow`
- `BusinessInterval`
- public exception types such as `ValidationError` and `CalendarConfigurationError`
- `WorkingCalendar`
- `UnionCalendar`
- `IntersectionCalendar`
- `DifferenceCalendar`
- `OverrideCalendar`
- `CalendarBuilder`
- `BusinessCalendar`
- `HolidayProvider`
- deadline helpers such as `deadline_for(...)` and `due_on_next_business_day(...)`
- policy types such as `BusinessDurationPolicy`, `BusinessDaysPolicy`, and `CutoffPolicy`

Stable Django-specific imports are exposed from `django_bizcal.django_api` for:

- calendar service resolution
- deadline-policy service resolution
- optional persistence helpers and models
- deadline-policy lookup and execution

Supporting modules remain importable, but these package-level surfaces are the stable API contract.
