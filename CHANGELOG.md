# Changelog

## 0.2.1

- Added a stable Django-specific public surface in `django_bizcal.django_api` for persistence and service helpers.
- Added selective named-calendar cache invalidation so persisted holiday changes only evict the affected logical calendar.
- Added admin and migration smoke coverage for the optional Django persistence layer.
- Expanded Django integration documentation with recommended import paths and cache behavior guidance.

## 0.2.0

- Added a more ergonomic calendar API with business-day iteration, counting, opening and closing helpers, and typed declarative config exports.
- Added `CalendarBuilder.to_dict(...)` for normalized round-trip serialization of working and composite calendars.
- Added named calendar registry support for Django via `BIZCAL_CALENDARS`, `BIZCAL_DEFAULT_CALENDAR_NAME`, `get_calendar(...)`, and cached multi-calendar service resolution.
- Added optional Django persistence for full-day holiday closures with the `CalendarHoliday` model, `DatabaseHolidayProvider`, admin registration, and automatic application to named calendars when `BIZCAL_ENABLE_DB_MODELS=True`.
- Added Django service helpers for managing persisted holidays, including `set_calendar_holiday(...)`, `sync_calendar_holidays(...)`, activation, deactivation, deletion, and cache invalidation.
- Expanded the test suite to cover edge cases, API ergonomics, multi-calendar Django integration, and database-backed holiday persistence.

## 0.1.2

- Hardened the GitHub release workflow for Trusted Publishing.
- Documented the recommended PyPI Trusted Publishing setup and fallback flow.
- Updated release guidance in the README.

## 0.1.1

- Marked the package as typed with `py.typed`.
- Aligned repository metadata with the public GitHub repository.
- Improved release hygiene by ignoring `dist-pypi/`.
- Added repository maintenance templates for issues and pull requests.
- Refreshed the README with badges and sponsorship guidance.

## 0.1.0

- Initial release of `django-bizcal`.
- Added pure business calendar domain with holiday providers and composable calendars.
- Added Django reusable app integration, settings wrapper, services, tests, documentation, and CI workflows.
