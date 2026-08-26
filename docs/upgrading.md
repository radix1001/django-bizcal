# Upgrading

## 0.11.0

Additive release for work blocks that cross midnight. No configuration change is required,
and a calendar without overnight blocks behaves and serializes exactly as in `0.10.1`.

What to check when upgrading:

- Run `python manage.py migrate django_bizcal` if the optional persistence models are
  enabled. Migration `0003_overnight_blocks` adds `CalendarDayOverrideWindow.end_offset_days`
  with a default of `0` and replaces the window check constraint with one that also allows
  `end_time <= start_time` when `end_offset_days = 1`.
- `WorkingCalendar.weekly_schedule`, `WorkingCalendar.day_overrides`, and
  `OverrideCalendar.overrides` now expose `ScheduleBlock` values instead of `TimeWindow`
  values. `ScheduleBlock` keeps the `start` and `end` attributes and adds `end_offset_days`,
  so attribute access is unchanged; code that does `isinstance(..., TimeWindow)` on these
  properties, or compares them against `TimeWindow` instances, needs updating.
  `ScheduleBlock.as_time_window()` converts an intraday block back.
- The same substitution applies to the persisted-override helpers
  `get_calendar_day_override_windows(...)` and `list_calendar_day_override_windows(...)`.
- Inputs are unchanged: a `TimeWindow`, a `(start, end)` pair, or the new
  `(start, end, end_offset_days)` triple are all accepted wherever a schedule is configured.
- If you previously modelled an overnight shift by splitting it across two days, replace the
  pair with a single `(start, end, 1)` block. That removes the one-second gap at midnight
  that made `business_time_between(...)` under-report the shift by one second.
- Review call sites of `opening_for_day(...)`, `closing_for_day(...)`,
  `next_opening_datetime(...)`, and `previous_closing_datetime(...)` if you adopt overnight
  blocks: they report civil-day boundaries, so they return midnight while a block is open
  across it. `WorkingCalendar.business_blocks_for_day(...)` returns the whole block.

## 0.10.1

`0.10.1` finishes the pre-`1.0.0` API-contract cleanup.

Compatibility changes:

- the package dependency range now targets maintained Django releases from `5.2` through `6.0`
- Django `4.2` is removed from the advertised and tested support matrix

Public API changes:

- `BizcalError`, `ValidationError`, `CalendarConfigurationError`, `CalendarRangeError`, and `TimezoneError` are now exported from the stable package-level API
- the official Django integration docs now consistently use `django_bizcal.django_api` instead of internal module imports

Upgrade guidance:

- if your project is still pinned to Django `4.2`, stay on `0.10.0` until you upgrade Django
- prefer `from django_bizcal import ...` and `from django_bizcal.django_api import ...` in application code going forward

## 0.10.0

`0.10.0` was the broad compatibility and release-hardening step that set up the final pre-`1.0.0` polish releases.

Compatibility changes:

- the package dependency range now allows Django releases through `6.0`
- package metadata now advertises Django `4.2`, `5.2`, and `6.0`
- package metadata now advertises Python `3.14`

Project guidance:

- see `docs/stability.md` for the stable import surfaces and the tested support matrix
- CI now validates `ruff`, `mypy`, `build`, and `twine check` outside the test matrix, so release readiness is checked continuously
- use `examples/performance_benchmark.py` when you want a quick local signal for hot-path performance after changes

## 0.7.0

`0.7.0` expanded the deadline-policy layer with `BusinessDaysPolicy`.

Upgrade notes:

- existing `BusinessDaysAtClosePolicy` usage remains valid
- `type="business_days_at_close"` remains supported
- use `type="business_days"` when you need opening, closing, or fixed wall-clock targets after multiple business-day boundaries

## 0.8.0

`0.8.0` added contextual deadline-policy resolution in the Django integration.

New optional setting:

- `BIZCAL_DEADLINE_POLICY_RESOLVER`

New Django APIs:

- `DeadlinePolicyResolution`
- `resolve_deadline_policy_for(...)`
- `get_deadline_policy_for(...)`
- `reset_deadline_policy_cache(...)`

Upgrade guidance:

- no migration is required
- existing `BIZCAL_DEADLINE_POLICIES`, `get_deadline_policy(name)`, and `compute_deadline("named_policy", ...)` code keeps working
- use `compute_deadline(policy_name=None, ...)` only when you want policy selection to come from shared business context

## 0.9.0

`0.9.0` focuses on stabilization rather than new product surface.

Behavioral changes:

- calendar instances now memoize local business windows per day with a bounded cache
- resolved Django settings are now cached process-locally for reuse
- `reset_calendar_cache()` and `reset_deadline_policy_cache()` clear the cached settings snapshot on global resets
- public API tests now enforce the exact stable export surface of `django_bizcal` and `django_bizcal.django_api`

Upgrade guidance:

- reusing calendar instances is now even more valuable in hot paths because repeated day queries benefit from per-instance memoization
- if your tests mutate Django settings dynamically, keep calling `reset_calendar_cache()` before rebuilding calendars or policies
- if your tests only mutate deadline-policy settings, `reset_deadline_policy_cache()` is sufficient
- no import-path changes are required
