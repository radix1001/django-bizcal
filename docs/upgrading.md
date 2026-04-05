# Upgrading

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
