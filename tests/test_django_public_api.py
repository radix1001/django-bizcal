from __future__ import annotations

import django_bizcal.django_api as django_api
from django_bizcal.django_api import (
    BusinessDaysAtClosePolicy,
    BusinessDaysPolicy,
    BusinessDeadline,
    BusinessDurationPolicy,
    CalendarDayOverride,
    CalendarDayOverrideWindow,
    CalendarHoliday,
    CalendarResolution,
    CloseOfBusinessPolicy,
    CutoffPolicy,
    DatabaseDayOverrideProvider,
    DatabaseHolidayProvider,
    DeadlinePolicy,
    DeadlinePolicyBuilder,
    DeadlinePolicyResolution,
    NextBusinessDayPolicy,
    SameBusinessDayPolicy,
    activate_calendar_day_override,
    activate_calendar_holiday,
    apply_database_holiday_overrides,
    apply_database_overrides,
    breach_at,
    build_calendar,
    build_deadline_policy,
    business_deadline_at_close,
    compute_deadline,
    deactivate_calendar_day_override,
    deactivate_calendar_holiday,
    deadline_for,
    delete_calendar_day_override,
    delete_calendar_holiday,
    due_on_next_business_day,
    get_calendar,
    get_calendar_day_override,
    get_calendar_day_override_windows,
    get_calendar_for,
    get_calendar_holiday,
    get_deadline_policy,
    get_deadline_policy_config,
    get_deadline_policy_for,
    get_default_calendar,
    is_breached,
    list_calendar_day_override_windows,
    list_calendar_day_overrides,
    list_calendar_holiday_days,
    list_calendar_holidays,
    list_configured_calendars,
    list_configured_deadline_policies,
    now,
    remaining_business_time,
    reset_calendar_cache,
    reset_deadline_policy_cache,
    resolve_calendar_for,
    resolve_deadline_policy_for,
    set_calendar_day_override,
    set_calendar_holiday,
    sync_calendar_day_overrides,
    sync_calendar_holidays,
)

EXPECTED_DJANGO_PUBLIC_API = {
    "CalendarDayOverride",
    "CalendarDayOverrideWindow",
    "CalendarHoliday",
    "CalendarResolution",
    "DeadlinePolicyResolution",
    "BusinessDaysAtClosePolicy",
    "BusinessDaysPolicy",
    "BusinessDeadline",
    "BusinessDurationPolicy",
    "CloseOfBusinessPolicy",
    "CutoffPolicy",
    "DatabaseDayOverrideProvider",
    "DatabaseHolidayProvider",
    "DeadlinePolicy",
    "DeadlinePolicyBuilder",
    "NextBusinessDayPolicy",
    "SameBusinessDayPolicy",
    "activate_calendar_day_override",
    "activate_calendar_holiday",
    "apply_database_holiday_overrides",
    "apply_database_overrides",
    "breach_at",
    "build_calendar",
    "build_deadline_policy",
    "business_deadline_at_close",
    "compute_deadline",
    "deactivate_calendar_day_override",
    "deactivate_calendar_holiday",
    "deadline_for",
    "delete_calendar_day_override",
    "delete_calendar_holiday",
    "due_on_next_business_day",
    "get_calendar",
    "get_deadline_policy_config",
    "get_deadline_policy",
    "get_deadline_policy_for",
    "get_calendar_for",
    "get_calendar_day_override",
    "get_calendar_day_override_windows",
    "get_calendar_holiday",
    "get_default_calendar",
    "list_calendar_day_overrides",
    "list_calendar_day_override_windows",
    "list_calendar_holiday_days",
    "list_calendar_holidays",
    "list_configured_calendars",
    "list_configured_deadline_policies",
    "now",
    "reset_calendar_cache",
    "reset_deadline_policy_cache",
    "resolve_calendar_for",
    "resolve_deadline_policy_for",
    "is_breached",
    "remaining_business_time",
    "set_calendar_day_override",
    "set_calendar_holiday",
    "sync_calendar_day_overrides",
    "sync_calendar_holidays",
}


def test_django_api_exports_stable_helpers() -> None:
    assert BusinessDaysAtClosePolicy is not None
    assert BusinessDaysPolicy is not None
    assert BusinessDeadline is not None
    assert BusinessDurationPolicy is not None
    assert CalendarDayOverride is not None
    assert CalendarDayOverrideWindow is not None
    assert CalendarHoliday is not None
    assert CalendarResolution is not None
    assert DeadlinePolicyResolution is not None
    assert CloseOfBusinessPolicy is not None
    assert CutoffPolicy is not None
    assert DatabaseDayOverrideProvider is not None
    assert DatabaseHolidayProvider is not None
    assert DeadlinePolicy is not None
    assert DeadlinePolicyBuilder is not None
    assert NextBusinessDayPolicy is not None
    assert SameBusinessDayPolicy is not None
    assert activate_calendar_day_override is not None
    assert activate_calendar_holiday is not None
    assert apply_database_overrides is not None
    assert apply_database_holiday_overrides is not None
    assert breach_at is not None
    assert build_calendar is not None
    assert build_deadline_policy is not None
    assert business_deadline_at_close is not None
    assert compute_deadline is not None
    assert deactivate_calendar_day_override is not None
    assert deactivate_calendar_holiday is not None
    assert deadline_for is not None
    assert delete_calendar_day_override is not None
    assert delete_calendar_holiday is not None
    assert due_on_next_business_day is not None
    assert get_calendar is not None
    assert get_deadline_policy_config is not None
    assert get_deadline_policy is not None
    assert get_deadline_policy_for is not None
    assert get_calendar_for is not None
    assert get_calendar_day_override is not None
    assert get_calendar_day_override_windows is not None
    assert get_calendar_holiday is not None
    assert get_default_calendar is not None
    assert list_calendar_day_overrides is not None
    assert list_calendar_day_override_windows is not None
    assert list_calendar_holiday_days is not None
    assert list_calendar_holidays is not None
    assert list_configured_calendars is not None
    assert list_configured_deadline_policies is not None
    assert now is not None
    assert is_breached is not None
    assert remaining_business_time is not None
    assert reset_calendar_cache is not None
    assert reset_deadline_policy_cache is not None
    assert resolve_calendar_for is not None
    assert resolve_deadline_policy_for is not None
    assert set_calendar_day_override is not None
    assert set_calendar_holiday is not None
    assert sync_calendar_day_overrides is not None
    assert sync_calendar_holidays is not None
    assert set(django_api.__all__) == EXPECTED_DJANGO_PUBLIC_API
