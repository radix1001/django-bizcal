"""Declarative calendar builder."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import time
from typing import Any, cast

from .calendars.base import BusinessCalendar
from .calendars.composite import (
    DifferenceCalendar,
    IntersectionCalendar,
    OverrideCalendar,
    OverrideInput,
    UnionCalendar,
)
from .calendars.working import DayOverrideInput, WeeklyScheduleInput, WorkingCalendar
from .config import (
    CalendarConfig,
    DayOverrideConfig,
    DifferenceCalendarConfig,
    IntersectionCalendarConfig,
    OverrideCalendarConfig,
    TimePairConfig,
    UnionCalendarConfig,
    WeeklyScheduleConfig,
    WorkingCalendarConfig,
)
from .exceptions import CalendarConfigurationError
from .providers import (
    CompositeHolidayProvider,
    HolidayProvider,
    HolidaysProvider,
    SetHolidayProvider,
)
from .types import coerce_years


class CalendarBuilder:
    """Builder for constructing calendars from serializable dictionaries."""

    @classmethod
    def from_dict(
        cls,
        config: CalendarConfig | Mapping[str, Any],
        *,
        default_tz: str | None = None,
        default_country: str | None = None,
        preload_years: Sequence[int] | None = None,
    ) -> BusinessCalendar:
        """Construct a calendar from a serializable mapping."""
        if "type" not in config:
            raise CalendarConfigurationError("Calendar configuration requires a 'type' field.")
        calendar_type = str(config["type"]).strip().lower()
        if calendar_type == "working":
            return cls._build_working(
                config,
                default_tz=default_tz,
                default_country=default_country,
                preload_years=preload_years,
            )
        if calendar_type == "union":
            children = cls._build_children(config, default_tz, default_country, preload_years)
            return UnionCalendar(children, tz=config.get("tz"))
        if calendar_type == "intersection":
            children = cls._build_children(config, default_tz, default_country, preload_years)
            return IntersectionCalendar(children, tz=config.get("tz"))
        if calendar_type == "difference":
            base, subtract = cls._build_difference_children(
                config, default_tz, default_country, preload_years
            )
            return DifferenceCalendar(base, subtract, tz=config.get("tz"))
        if calendar_type == "override":
            base = cls.from_dict(
                cls._mapping(config.get("base"), field_name="base"),
                default_tz=default_tz,
                default_country=default_country,
                preload_years=preload_years,
            )
            overrides = cast(
                OverrideInput,
                cls._mapping(config.get("overrides"), field_name="overrides"),
            )
            return OverrideCalendar(base, overrides, tz=config.get("tz"))
        raise CalendarConfigurationError(f"Unsupported calendar type: {calendar_type!r}.")

    @classmethod
    def to_dict(cls, calendar: BusinessCalendar) -> CalendarConfig:
        """Serialize a supported calendar implementation into declarative config."""
        if isinstance(calendar, WorkingCalendar):
            return cls._serialize_working(calendar)
        if isinstance(calendar, UnionCalendar):
            return UnionCalendarConfig(
                type="union",
                tz=calendar.tz.key,
                children=[cls.to_dict(child) for child in calendar.children],
            )
        if isinstance(calendar, IntersectionCalendar):
            return IntersectionCalendarConfig(
                type="intersection",
                tz=calendar.tz.key,
                children=[cls.to_dict(child) for child in calendar.children],
            )
        if isinstance(calendar, DifferenceCalendar):
            return DifferenceCalendarConfig(
                type="difference",
                tz=calendar.tz.key,
                base=cls.to_dict(calendar.base),
                subtract=cls.to_dict(calendar.subtract),
            )
        if isinstance(calendar, OverrideCalendar):
            return OverrideCalendarConfig(
                type="override",
                tz=calendar.tz.key,
                base=cls.to_dict(calendar.base),
                overrides=cls._serialize_day_overrides(calendar.overrides),
            )
        raise CalendarConfigurationError(
            f"CalendarBuilder.to_dict does not support {calendar.__class__.__name__!r}."
        )

    @classmethod
    def _build_working(
        cls,
        config: Mapping[str, Any],
        *,
        default_tz: str | None,
        default_country: str | None,
        preload_years: Sequence[int] | None,
    ) -> WorkingCalendar:
        tz = config.get("tz") or default_tz
        if tz is None:
            raise CalendarConfigurationError("Working calendar requires a timezone.")
        weekly_schedule = cast(
            WeeklyScheduleInput,
            cls._mapping(
                config.get("weekly_schedule"),
                field_name="weekly_schedule",
            ),
        )
        country = config.get("country") or default_country
        years_value = config.get("years", preload_years)
        holiday_provider = cls._build_holiday_provider(
            country=country,
            years_value=years_value,
            subdivision=config.get("subdivision"),
            observed=bool(config.get("observed", True)),
            extra_holidays=config.get("extra_holidays", ()),
            custom_holidays=config.get("custom_holidays", ()),
        )
        return WorkingCalendar(
            tz=tz,
            weekly_schedule=weekly_schedule,
            holiday_provider=holiday_provider,
            day_overrides=cast(DayOverrideInput | None, config.get("day_overrides")),
            name=config.get("name"),
        )

    @classmethod
    def _build_holiday_provider(
        cls,
        *,
        country: str | None,
        years_value: int | Sequence[int] | None,
        subdivision: str | None,
        observed: bool,
        extra_holidays: Iterable[Any],
        custom_holidays: Iterable[Any],
    ) -> HolidayProvider | None:
        providers: list[HolidayProvider] = []
        if country is not None:
            if years_value is None:
                raise CalendarConfigurationError(
                    "Country-based holiday configuration requires explicit years or preload years."
                )
            providers.append(
                HolidaysProvider.from_country(
                    country=country,
                    years=coerce_years(years_value),
                    subdivision=subdivision,
                    observed=observed,
                )
            )
        merged_custom = tuple(extra_holidays) + tuple(custom_holidays)
        if merged_custom:
            providers.append(SetHolidayProvider.from_dates(merged_custom))
        return CompositeHolidayProvider.combine(providers)

    @classmethod
    def _build_children(
        cls,
        config: Mapping[str, Any],
        default_tz: str | None,
        default_country: str | None,
        preload_years: Sequence[int] | None,
    ) -> tuple[BusinessCalendar, ...]:
        children_config = config.get("children")
        if not isinstance(children_config, Sequence) or isinstance(children_config, (str, bytes)):
            raise CalendarConfigurationError(
                "'children' must be a sequence of calendar definitions."
            )
        return tuple(
            cls.from_dict(
                cls._mapping(item, field_name="child"),
                default_tz=default_tz,
                default_country=default_country,
                preload_years=preload_years,
            )
            for item in children_config
        )

    @classmethod
    def _build_difference_children(
        cls,
        config: Mapping[str, Any],
        default_tz: str | None,
        default_country: str | None,
        preload_years: Sequence[int] | None,
    ) -> tuple[BusinessCalendar, BusinessCalendar]:
        if "base" in config and "subtract" in config:
            return (
                cls.from_dict(
                    cls._mapping(config.get("base"), field_name="base"),
                    default_tz=default_tz,
                    default_country=default_country,
                    preload_years=preload_years,
                ),
                cls.from_dict(
                    cls._mapping(config.get("subtract"), field_name="subtract"),
                    default_tz=default_tz,
                    default_country=default_country,
                    preload_years=preload_years,
                ),
            )
        children = cls._build_children(config, default_tz, default_country, preload_years)
        if len(children) != 2:
            raise CalendarConfigurationError(
                "Difference calendar requires exactly two child calendars "
                "or explicit base/subtract."
            )
        return children[0], children[1]

    @staticmethod
    def _mapping(value: Any, *, field_name: str) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise CalendarConfigurationError(f"'{field_name}' must be a mapping.")
        return value

    @classmethod
    def _serialize_working(cls, calendar: WorkingCalendar) -> WorkingCalendarConfig:
        config: WorkingCalendarConfig = WorkingCalendarConfig(
            type="working",
            tz=calendar.tz.key,
            weekly_schedule=cls._serialize_weekly_schedule(calendar.weekly_schedule),
        )
        holiday_config = cls._serialize_holiday_provider(calendar.holiday_provider)
        if "country" in holiday_config:
            config["country"] = cast(str, holiday_config["country"])
        if "years" in holiday_config:
            config["years"] = cast(list[int], holiday_config["years"])
        if "subdivision" in holiday_config and holiday_config["subdivision"] is not None:
            config["subdivision"] = cast(str, holiday_config["subdivision"])
        if "observed" in holiday_config:
            config["observed"] = cast(bool, holiday_config["observed"])
        if "extra_holidays" in holiday_config:
            config["extra_holidays"] = cast(list[str], holiday_config["extra_holidays"])
        if calendar.day_overrides:
            config["day_overrides"] = cls._serialize_day_overrides(calendar.day_overrides)
        if calendar.name is not None:
            config["name"] = calendar.name
        return config

    @classmethod
    def _serialize_holiday_provider(
        cls,
        provider: HolidayProvider | None,
    ) -> dict[str, Any]:
        if provider is None:
            return {}
        if isinstance(provider, HolidaysProvider):
            payload: dict[str, Any] = {
                "country": provider.country,
                "years": list(provider.years),
            }
            if provider.subdivision is not None:
                payload["subdivision"] = provider.subdivision
            if provider.observed is not True:
                payload["observed"] = provider.observed
            return payload
        if isinstance(provider, SetHolidayProvider):
            return {
                "extra_holidays": [current.isoformat() for current in sorted(provider.days)],
            }
        if isinstance(provider, CompositeHolidayProvider):
            combined_payload: dict[str, Any] = {}
            extra_holidays: list[str] = []
            for current in provider.providers:
                if isinstance(current, HolidaysProvider):
                    if "country" in combined_payload:
                        raise CalendarConfigurationError(
                            "Multiple official holiday providers are not serializable."
                        )
                    combined_payload.update(cls._serialize_holiday_provider(current))
                elif isinstance(current, SetHolidayProvider):
                    extra_holidays.extend(
                        current_day.isoformat() for current_day in sorted(current.days)
                    )
                else:
                    raise CalendarConfigurationError(
                        f"Unsupported holiday provider {current.__class__.__name__!r}."
                    )
            if extra_holidays:
                combined_payload["extra_holidays"] = sorted(set(extra_holidays))
            return combined_payload
        raise CalendarConfigurationError(
            f"Unsupported holiday provider {provider.__class__.__name__!r}."
        )

    @staticmethod
    def _serialize_weekly_schedule(
        schedule: Mapping[int, Sequence[Any]],
    ) -> WeeklyScheduleConfig:
        serialized: WeeklyScheduleConfig = {}
        for weekday, windows in schedule.items():
            serialized[str(weekday)] = [
                CalendarBuilder._serialize_time_pair(
                    window.start,
                    window.end,
                )
                for window in windows
            ]
        return serialized

    @staticmethod
    def _serialize_day_overrides(
        overrides: Mapping[Any, Sequence[Any]],
    ) -> DayOverrideConfig:
        serialized: DayOverrideConfig = {}
        for day, windows in overrides.items():
            serialized[day.isoformat()] = (
                None
                if not windows
                else [
                    CalendarBuilder._serialize_time_pair(
                        window.start,
                        window.end,
                    )
                    for window in windows
                ]
            )
        return serialized

    @staticmethod
    def _serialize_time_pair(start: time, end: time) -> TimePairConfig:
        return (
            CalendarBuilder._serialize_time_value(start),
            CalendarBuilder._serialize_time_value(end),
        )

    @staticmethod
    def _serialize_time_value(value: time) -> str:
        if value.second == 0 and value.microsecond == 0:
            return value.strftime("%H:%M")
        return value.replace(microsecond=0).isoformat()
