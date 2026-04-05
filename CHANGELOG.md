# Changelog

## 0.8.0

- Added contextual deadline-policy resolution for Django through `BIZCAL_DEADLINE_POLICY_RESOLVER`, `DeadlinePolicyResolution`, `resolve_deadline_policy_for(...)`, and `get_deadline_policy_for(...)`.
- Extended `compute_deadline(...)` so `policy_name=None` can resolve the deadline policy from the same contextual inputs already used for calendar resolution.
- Added targeted deadline-policy cache management with `reset_deadline_policy_cache(...)`, while keeping global `reset_calendar_cache()` behavior backward compatible for settings reload scenarios.
- Expanded examples, docs, settings coverage, and Django integration tests for contextual SLA-policy selection by tenant, priority, and workflow context.

## 0.7.0

- Added `BusinessDaysPolicy` so declarative deadline rules can target the opening, closing, or a fixed snapped wall-clock time after an arbitrary number of business-day boundaries.
- Kept `BusinessDaysAtClosePolicy` fully backward compatible while reusing the same internal boundary-counting semantics as the new generalized policy.
- Hardened deadline-policy validation by rejecting negative mixed duration components and by validating that cutoff branches are declarative policy mappings.
- Expanded the stable public API exports, Django integration coverage, documentation, and examples for the generalized business-days policy.
- Updated the architecture guide to reflect the stable public API surface that now includes deadline helpers and declarative policy types.

## 0.6.0

- Added a declarative deadline-policy layer with `BusinessDurationPolicy`, `CloseOfBusinessPolicy`, `NextBusinessDayPolicy`, `BusinessDaysAtClosePolicy`, `CutoffPolicy`, and `SameBusinessDayPolicy`.
- Added `DeadlinePolicyBuilder.from_dict(...)` and `DeadlinePolicyBuilder.to_dict(...)` for typed, serializable deadline-policy configuration.
- Added calendar-bound helpers such as `resolve_deadline_policy(...)` and `resolve_deadline_policy_dict(...)` so business calendars can evaluate policies directly.
- Added Django settings and services for named deadline policies via `BIZCAL_DEADLINE_POLICIES`, `get_deadline_policy(...)`, `get_deadline_policy_config(...)`, `build_deadline_policy(...)`, `list_configured_deadline_policies(...)`, and `compute_deadline(...)`.
- Expanded the stable public API, test suite, examples, and documentation to cover declarative deadline policies for named and contextual Django calendars.

## 0.5.0

- Added `BusinessDeadline` plus SLA- and due-date helpers such as `deadline_for(...)`, `breach_at(...)`, `remaining_business_time(...)`, `due_on_next_business_day(...)`, and `business_deadline_at_close(...)`.
- Added stable exports for the deadline helpers from both `django_bizcal` and `django_bizcal.django_api`.
- Added tests, examples, and documentation for business-deadline workflows on top of named and contextual Django calendars.

## 0.4.0

- Added contextual Django calendar resolution through `BIZCAL_CALENDAR_RESOLVER`, `CalendarResolution`, `resolve_calendar_for(...)`, and `get_calendar_for(...)`.
- Added support for resolver outputs that return either named calendars or ad hoc calendar configs, with optional contextual memoization via `cache_key`.
- Added selective invalidation of contextual calendar cache entries when persisted holiday or day-override changes affect the same logical calendar name.
- Expanded the stable Django-specific public API, tests, examples, and documentation for multi-tenant, client, and region-aware calendar lookup patterns.

## 0.3.0

- Added persisted per-day schedule overrides for named Django calendars with the `CalendarDayOverride` and `CalendarDayOverrideWindow` models.
- Added `DatabaseDayOverrideProvider` and merged runtime application of persisted holiday closures plus per-day intraday overrides.
- Added Django service helpers for day-override CRUD and sync workflows, including selective cache invalidation for the affected logical calendar.
- Added automatic named-calendar cache invalidation for persisted changes coming from service helpers, Django admin, and direct ORM saves/deletes after transaction commit.
- Added admin UX improvements for persisted overrides, including window summaries, date hierarchy, read-only timestamps, and bulk activate/deactivate actions.
- Added read-oriented Django service helpers for inspecting persisted holiday dates and normalized override windows without traversing ORM relations directly.
- Fixed review findings in the DB override layer by removing an `N+1` query path, normalizing public provider names consistently, and hardening migration tests against future migrations.
- Added admin, migration, and integration coverage for persisted intraday day overrides and persistence cache behavior.
- Expanded the Django-specific public API, examples, and documentation to cover database-backed intraday override workflows and operational behavior.

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
