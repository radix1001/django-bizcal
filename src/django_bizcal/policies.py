"""Declarative deadline policy layer built on top of business calendars."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any, Protocol, cast

from .calendars.base import BusinessCalendar
from .config import (
    BusinessDaysAtClosePolicyConfig,
    BusinessDurationPolicyConfig,
    CloseOfBusinessPolicyConfig,
    CutoffPolicyConfig,
    DeadlinePolicyConfig,
    NextBusinessDayPolicyConfig,
    SameBusinessDayPolicyConfig,
)
from .deadlines import (
    BusinessDeadline,
    _coerce_local_day,
    _resolve_day_deadline,
    deadline_for,
    due_on_next_business_day,
)
from .exceptions import ValidationError
from .types import TimeInput, coerce_time, ensure_aware


class DeadlinePolicy(Protocol):
    """Protocol for declarative policies that compute business deadlines."""

    def resolve(
        self,
        start: datetime,
        *,
        calendar: BusinessCalendar,
        calendar_name: str | None = None,
    ) -> BusinessDeadline: ...


@dataclass(frozen=True, slots=True)
class BusinessDurationPolicy:
    """Policy that adds a business duration to the starting datetime."""

    service_time: timedelta

    def __post_init__(self) -> None:
        if self.service_time < timedelta(0):
            raise ValidationError("service_time must not be negative.")

    def resolve(
        self,
        start: datetime,
        *,
        calendar: BusinessCalendar,
        calendar_name: str | None = None,
    ) -> BusinessDeadline:
        return deadline_for(
            start,
            self.service_time,
            calendar=calendar,
            calendar_name=calendar_name,
        )


@dataclass(frozen=True, slots=True)
class CloseOfBusinessPolicy:
    """Policy that resolves to the current business day's closing boundary."""

    def resolve(
        self,
        start: datetime,
        *,
        calendar: BusinessCalendar,
        calendar_name: str | None = None,
    ) -> BusinessDeadline:
        normalized_start = ensure_aware(start, param_name="start")
        local_day = _coerce_local_day(normalized_start, calendar)
        target_day = calendar.next_business_day(local_day)
        resolved_deadline = _resolve_day_deadline(
            target_day,
            calendar=calendar,
            at="closing",
            tz=None,
        )
        if resolved_deadline < normalized_start:
            target_day = calendar.next_business_day(target_day + timedelta(days=1))
            resolved_deadline = _resolve_day_deadline(
                target_day,
                calendar=calendar,
                at="closing",
                tz=None,
            )
        return _build_policy_deadline(
            normalized_start,
            resolved_deadline,
            calendar=calendar,
            calendar_name=calendar_name,
        )


@dataclass(frozen=True, slots=True)
class NextBusinessDayPolicy:
    """Policy that resolves to a boundary on the next business day."""

    at: str | TimeInput = "opening"
    tz: str | None = None

    def __post_init__(self) -> None:
        if self.at not in {"opening", "closing"}:
            object.__setattr__(self, "at", coerce_time(self.at))

    def resolve(
        self,
        start: datetime,
        *,
        calendar: BusinessCalendar,
        calendar_name: str | None = None,
    ) -> BusinessDeadline:
        normalized_start = ensure_aware(start, param_name="start")
        resolved_deadline = due_on_next_business_day(
            normalized_start,
            calendar=calendar,
            at=self.at,
            tz=self.tz,
        )
        return _build_policy_deadline(
            normalized_start,
            resolved_deadline,
            calendar=calendar,
            calendar_name=calendar_name,
        )


@dataclass(frozen=True, slots=True)
class SameBusinessDayPolicy:
    """Policy that resolves on the current business day, else rolls to the next one."""

    at: str | TimeInput = "closing"
    tz: str | None = None

    def __post_init__(self) -> None:
        if self.at not in {"opening", "closing"}:
            object.__setattr__(self, "at", coerce_time(self.at))

    def resolve(
        self,
        start: datetime,
        *,
        calendar: BusinessCalendar,
        calendar_name: str | None = None,
    ) -> BusinessDeadline:
        normalized_start = ensure_aware(start, param_name="start")
        local_day = _coerce_local_day(normalized_start, calendar)
        target_day = calendar.next_business_day(local_day)
        resolved_deadline = _resolve_day_deadline(
            target_day,
            calendar=calendar,
            at=self.at,
            tz=self.tz,
        )
        if resolved_deadline < normalized_start:
            target_day = calendar.next_business_day(target_day + timedelta(days=1))
            resolved_deadline = _resolve_day_deadline(
                target_day,
                calendar=calendar,
                at=self.at,
                tz=self.tz,
            )
        return _build_policy_deadline(
            normalized_start,
            resolved_deadline,
            calendar=calendar,
            calendar_name=calendar_name,
        )


@dataclass(frozen=True, slots=True)
class BusinessDaysAtClosePolicy:
    """Policy that resolves after a number of business-day closing boundaries."""

    business_days: int
    include_start: bool = False
    tz: str | None = None

    def __post_init__(self) -> None:
        if self.business_days <= 0:
            raise ValidationError("business_days must be a positive integer.")

    def resolve(
        self,
        start: datetime,
        *,
        calendar: BusinessCalendar,
        calendar_name: str | None = None,
    ) -> BusinessDeadline:
        normalized_start = ensure_aware(start, param_name="start")
        local_day = _coerce_local_day(normalized_start, calendar)
        remaining_boundaries = self.business_days
        search_from = local_day if self.include_start else local_day + timedelta(days=1)

        while True:
            target_day = calendar.next_business_day(search_from)
            resolved_deadline = _resolve_day_deadline(
                target_day,
                calendar=calendar,
                at="closing",
                tz=self.tz,
            )
            if resolved_deadline >= normalized_start:
                remaining_boundaries -= 1
                if remaining_boundaries == 0:
                    break
            search_from = target_day + timedelta(days=1)
        return _build_policy_deadline(
            normalized_start,
            resolved_deadline,
            calendar=calendar,
            calendar_name=calendar_name,
        )


@dataclass(frozen=True, slots=True)
class CutoffPolicy:
    """Policy that dispatches to another policy depending on a local cutoff time."""

    cutoff: TimeInput
    before: DeadlinePolicy
    after: DeadlinePolicy

    def __post_init__(self) -> None:
        object.__setattr__(self, "cutoff", coerce_time(self.cutoff))

    def resolve(
        self,
        start: datetime,
        *,
        calendar: BusinessCalendar,
        calendar_name: str | None = None,
    ) -> BusinessDeadline:
        normalized_start = ensure_aware(start, param_name="start")
        local_start = normalized_start.astimezone(calendar.tz)
        cutoff = cast(time, self.cutoff)
        branch = (
            self.before
            if local_start.timetz().replace(tzinfo=None) <= cutoff
            else self.after
        )
        return branch.resolve(
            normalized_start,
            calendar=calendar,
            calendar_name=calendar_name,
        )


class DeadlinePolicyBuilder:
    """Builder for declarative deadline policies."""

    @classmethod
    def from_dict(
        cls,
        config: DeadlinePolicyConfig | Mapping[str, Any],
    ) -> DeadlinePolicy:
        if not isinstance(config, Mapping):
            raise ValidationError("Deadline policy config must be a mapping.")
        raw_config = cast(Mapping[str, Any], dict(config))
        policy_type = str(raw_config.get("type", "")).strip()
        if not policy_type:
            raise ValidationError("Deadline policy config requires a non-empty type.")
        if policy_type == "business_duration":
            return cls._build_business_duration(raw_config)
        if policy_type == "close_of_business":
            return CloseOfBusinessPolicy()
        if policy_type == "next_business_day":
            return NextBusinessDayPolicy(
                at=cast(str, raw_config.get("at", "opening")),
                tz=cast(str | None, raw_config.get("tz")),
            )
        if policy_type == "same_business_day":
            return SameBusinessDayPolicy(
                at=cast(str, raw_config.get("at", "closing")),
                tz=cast(str | None, raw_config.get("tz")),
            )
        if policy_type == "business_days_at_close":
            if "business_days" not in raw_config:
                raise ValidationError(
                    "business_days_at_close policy requires business_days."
                )
            return BusinessDaysAtClosePolicy(
                business_days=int(raw_config["business_days"]),
                include_start=bool(raw_config.get("include_start", False)),
                tz=cast(str | None, raw_config.get("tz")),
            )
        if policy_type == "cutoff":
            if (
                "cutoff" not in raw_config
                or "before" not in raw_config
                or "after" not in raw_config
            ):
                raise ValidationError(
                    "cutoff policy requires cutoff, before, and after."
                )
            return CutoffPolicy(
                cutoff=cast(TimeInput, raw_config["cutoff"]),
                before=cls.from_dict(cast(Mapping[str, Any], raw_config["before"])),
                after=cls.from_dict(cast(Mapping[str, Any], raw_config["after"])),
            )
        raise ValidationError(f"Unsupported deadline policy type: {policy_type!r}.")

    @classmethod
    def to_dict(cls, policy: DeadlinePolicy) -> DeadlinePolicyConfig:
        """Serialize a supported policy back into declarative configuration."""
        if isinstance(policy, BusinessDurationPolicy):
            return cls._serialize_business_duration(policy)
        if isinstance(policy, CloseOfBusinessPolicy):
            return CloseOfBusinessPolicyConfig(type="close_of_business")
        if isinstance(policy, NextBusinessDayPolicy):
            next_config: NextBusinessDayPolicyConfig = {
                "type": "next_business_day",
                "at": _serialize_boundary(policy.at),
            }
            if policy.tz is not None:
                next_config["tz"] = policy.tz
            return next_config
        if isinstance(policy, SameBusinessDayPolicy):
            same_day_config: SameBusinessDayPolicyConfig = {
                "type": "same_business_day",
                "at": _serialize_boundary(policy.at),
            }
            if policy.tz is not None:
                same_day_config["tz"] = policy.tz
            return same_day_config
        if isinstance(policy, BusinessDaysAtClosePolicy):
            close_config: BusinessDaysAtClosePolicyConfig = {
                "type": "business_days_at_close",
                "business_days": policy.business_days,
            }
            if policy.include_start:
                close_config["include_start"] = True
            if policy.tz is not None:
                close_config["tz"] = policy.tz
            return close_config
        if isinstance(policy, CutoffPolicy):
            return CutoffPolicyConfig(
                type="cutoff",
                cutoff=_serialize_time(policy.cutoff),
                before=cls.to_dict(policy.before),
                after=cls.to_dict(policy.after),
            )
        raise ValidationError(
            f"DeadlinePolicyBuilder.to_dict does not support {type(policy).__name__!r}."
        )

    @staticmethod
    def _build_business_duration(config: Mapping[str, Any]) -> BusinessDurationPolicy:
        if "business_hours" not in config and "business_minutes" not in config:
            raise ValidationError(
                "business_duration policy requires business_hours or business_minutes."
            )
        service_time = timedelta()
        if "business_hours" in config:
            service_time += timedelta(hours=float(config["business_hours"]))
        if "business_minutes" in config:
            service_time += timedelta(minutes=int(config["business_minutes"]))
        return BusinessDurationPolicy(service_time=service_time)

    @staticmethod
    def _serialize_business_duration(
        policy: BusinessDurationPolicy,
    ) -> BusinessDurationPolicyConfig:
        total_seconds = policy.service_time.total_seconds()
        if total_seconds % 3600 == 0:
            return BusinessDurationPolicyConfig(
                type="business_duration",
                business_hours=int(total_seconds // 3600),
            )
        if total_seconds % 60 == 0:
            return BusinessDurationPolicyConfig(
                type="business_duration",
                business_minutes=int(total_seconds // 60),
            )
        return BusinessDurationPolicyConfig(
            type="business_duration",
            business_hours=total_seconds / 3600.0,
        )


def _build_policy_deadline(
    start: datetime,
    deadline: datetime,
    *,
    calendar: BusinessCalendar,
    calendar_name: str | None,
) -> BusinessDeadline:
    normalized_start = ensure_aware(start, param_name="start")
    normalized_deadline = ensure_aware(deadline, param_name="deadline")
    return BusinessDeadline(
        start=normalized_start,
        service_time=calendar.business_time_between(normalized_start, normalized_deadline),
        deadline=normalized_deadline,
        calendar=calendar,
        calendar_name=calendar_name or calendar.calendar_name,
    )


def _serialize_boundary(value: str | TimeInput) -> str:
    if value in {"opening", "closing"}:
        return cast(str, value)
    return _serialize_time(cast(time, value))


def _serialize_time(value: TimeInput) -> str:
    resolved = coerce_time(value)
    if resolved.second == 0 and resolved.microsecond == 0:
        return resolved.strftime("%H:%M")
    return resolved.isoformat()
