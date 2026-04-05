"""Context-aware resolution helpers for Django integration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias, cast

from .config import CalendarConfig, DeadlinePolicyConfig
from .exceptions import CalendarConfigurationError

if TYPE_CHECKING:
    from .settings import BizcalSettings

ContextInput: TypeAlias = Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class CalendarResolution:
    """Resolved contextual calendar target for Django service resolution.

    `name` identifies a logical calendar name and is also used as the persisted
    override key when database models are enabled.
    `config` optionally provides an explicit calendar config to build instead of
    looking up a named calendar from settings.
    `cache_key` enables memoization for config-based contextual calendars.
    """

    name: str | None = None
    config: CalendarConfig | None = None
    cache_key: str | None = None

    def __post_init__(self) -> None:
        normalized_name = _normalize_optional_value(
            self.name,
            resolution_name="CalendarResolution",
            field_name="name",
        )
        normalized_cache_key = _normalize_optional_value(
            self.cache_key,
            resolution_name="CalendarResolution",
            field_name="cache_key",
        )
        normalized_config = cast(CalendarConfig | None, dict(self.config) if self.config else None)
        if normalized_name is None and normalized_config is None:
            raise CalendarConfigurationError(
                "CalendarResolution requires at least a name or a config."
            )
        object.__setattr__(self, "name", normalized_name)
        object.__setattr__(self, "config", normalized_config)
        object.__setattr__(self, "cache_key", normalized_cache_key)

    @classmethod
    def for_name(cls, name: str) -> CalendarResolution:
        """Resolve to a named configured calendar."""
        return cls(name=name)

    @classmethod
    def for_config(
        cls,
        config: CalendarConfig | Mapping[str, Any],
        *,
        name: str | None = None,
        cache_key: str | None = None,
    ) -> CalendarResolution:
        """Resolve to an explicit calendar config, optionally with a logical name."""
        return cls(
            name=name,
            config=cast(CalendarConfig, dict(config)),
            cache_key=cache_key,
        )

CalendarResolverResult: TypeAlias = str | CalendarConfig | CalendarResolution


class CalendarResolver(Protocol):
    """Protocol for contextual Django calendar resolvers."""

    def __call__(
        self,
        *,
        context: ContextInput,
        bizcal_settings: BizcalSettings,
    ) -> CalendarResolverResult: ...


def normalize_calendar_resolution(result: CalendarResolverResult) -> CalendarResolution:
    """Normalize supported resolver outputs into a `CalendarResolution`."""
    if isinstance(result, CalendarResolution):
        return result
    if isinstance(result, str):
        return CalendarResolution.for_name(result)
    if isinstance(result, Mapping):
        return CalendarResolution.for_config(cast(CalendarConfig, dict(result)))
    raise CalendarConfigurationError(
        "BIZCAL_CALENDAR_RESOLVER must return a calendar name, "
        "a calendar config mapping, or CalendarResolution."
    )


@dataclass(frozen=True, slots=True)
class DeadlinePolicyResolution:
    """Resolved contextual deadline-policy target for Django service resolution."""

    name: str | None = None
    config: DeadlinePolicyConfig | None = None
    cache_key: str | None = None

    def __post_init__(self) -> None:
        normalized_name = _normalize_optional_value(
            self.name,
            resolution_name="DeadlinePolicyResolution",
            field_name="name",
        )
        normalized_cache_key = _normalize_optional_value(
            self.cache_key,
            resolution_name="DeadlinePolicyResolution",
            field_name="cache_key",
        )
        normalized_config = cast(
            DeadlinePolicyConfig | None,
            dict(self.config) if self.config else None,
        )
        if normalized_name is None and normalized_config is None:
            raise CalendarConfigurationError(
                "DeadlinePolicyResolution requires at least a name or a config."
            )
        object.__setattr__(self, "name", normalized_name)
        object.__setattr__(self, "config", normalized_config)
        object.__setattr__(self, "cache_key", normalized_cache_key)

    @classmethod
    def for_name(cls, name: str) -> DeadlinePolicyResolution:
        """Resolve to a named configured deadline policy."""
        return cls(name=name)

    @classmethod
    def for_config(
        cls,
        config: DeadlinePolicyConfig | Mapping[str, Any],
        *,
        name: str | None = None,
        cache_key: str | None = None,
    ) -> DeadlinePolicyResolution:
        """Resolve to an explicit deadline-policy config."""
        return cls(
            name=name,
            config=cast(DeadlinePolicyConfig, dict(config)),
            cache_key=cache_key,
        )


DeadlinePolicyResolverResult: TypeAlias = (
    str | DeadlinePolicyConfig | DeadlinePolicyResolution
)


class DeadlinePolicyResolver(Protocol):
    """Protocol for contextual Django deadline-policy resolvers."""

    def __call__(
        self,
        *,
        context: ContextInput,
        bizcal_settings: BizcalSettings,
    ) -> DeadlinePolicyResolverResult: ...


def normalize_deadline_policy_resolution(
    result: DeadlinePolicyResolverResult,
) -> DeadlinePolicyResolution:
    """Normalize supported resolver outputs into a `DeadlinePolicyResolution`."""
    if isinstance(result, DeadlinePolicyResolution):
        return result
    if isinstance(result, str):
        return DeadlinePolicyResolution.for_name(result)
    if isinstance(result, Mapping):
        return DeadlinePolicyResolution.for_config(cast(DeadlinePolicyConfig, dict(result)))
    raise CalendarConfigurationError(
        "BIZCAL_DEADLINE_POLICY_RESOLVER must return a deadline policy name, "
        "a deadline policy config mapping, or DeadlinePolicyResolution."
    )


def _normalize_optional_value(
    value: str | None,
    *,
    resolution_name: str,
    field_name: str,
) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        raise CalendarConfigurationError(
            f"{resolution_name} {field_name} must not be blank when provided."
        )
    return normalized
