# Production Usage

## Goals

`django-bizcal` is designed to be embedded in production Django services where
business-time behavior must stay predictable across:

- timezones
- official holidays
- one-off closures
- intraday overrides
- tenant or region specific calendar selection
- tenant or priority specific deadline-policy selection

## Recommended service-layer pattern

Keep business-calendar access behind your own application service layer.

Recommended calls:

- `get_default_calendar()` for single-calendar installations
- `get_calendar(name)` for named configured calendars
- `get_calendar_for(...)` for contextual calendar resolution
- `get_deadline_policy(name)` for named configured deadline policies
- `get_deadline_policy_for(...)` for contextual deadline-policy resolution
- `compute_deadline(...)` when you want one entry point that can resolve both context layers

This keeps request handlers, models, and workflow code from rebuilding calendar
and policy objects manually.

## Cache model

The Django integration keeps several process-local caches:

- bounded per-calendar local day-window memoization in the pure domain
- resolved settings
- named calendars
- contextual calendars keyed by resolver `cache_key`
- named deadline policies
- contextual deadline policies keyed by resolver `cache_key`

Operational guidance:

- reuse calendar objects instead of rebuilding them inside hot request or workflow paths
- use `reset_calendar_cache()` after changing Django settings in tests or local reload workflows
- use `reset_deadline_policy_cache()` when you only need to invalidate policy caches after policy-setting changes
- prefer targeted invalidation helpers for persisted holiday and day-override changes instead of manual cache resets

## Resolver design guidance

Keep resolvers thin and deterministic.

Good resolver responsibilities:

- normalize tenant, region, priority, or workflow inputs
- map those inputs to a stable logical name
- return a config only when the object is genuinely contextual
- provide a `cache_key` whenever contextual reuse is expected

Avoid putting heavy I/O, ORM traversal, or business workflows directly inside resolvers.

## Timezone and year policy

Production deployments should make timezone and holiday horizons explicit:

- set `BIZCAL_DEFAULT_TIMEZONE`
- set `BIZCAL_PRELOAD_YEARS` to a deliberate value
- preload enough years for your SLA horizon and reporting windows

If a deployment crosses into years outside the configured horizon, holiday behavior
may no longer reflect the intended official calendar.

## Persistence scope

The optional Django models are intentionally small in scope:

- `CalendarHoliday`
- `CalendarDayOverride`
- `CalendarDayOverrideWindow`

Use them for operational closures and special schedules, not for full calendar-definition storage.

## Observability and troubleshooting

When investigating a deadline issue, capture:

- input datetime with timezone
- resolved calendar name
- resolved deadline-policy name, if one exists
- business windows for the relevant day
- persisted holiday or override rows for the logical calendar name

This is usually enough to determine whether the issue came from context resolution,
holiday data, override data, or deadline-policy selection.

## Limits

`django-bizcal` intentionally does not yet provide:

- ORM persistence for full calendar graphs
- ORM persistence for full deadline-policy graphs
- distributed cache coordination across processes

If you run many app processes, each process keeps its own in-memory cache and must
observe the same persisted source of truth.
