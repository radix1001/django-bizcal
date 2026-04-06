# Upgrading

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
