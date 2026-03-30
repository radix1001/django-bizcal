"""Holiday providers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from functools import cached_property
from typing import Protocol, runtime_checkable

import holidays

from .exceptions import CalendarRangeError
from .types import DateInput, coerce_date, coerce_years


@runtime_checkable
class HolidayProvider(Protocol):
    """Protocol for querying holidays by date."""

    def is_holiday(self, day: date) -> bool:
        """Return whether the given day is a holiday."""


@dataclass(frozen=True, slots=True)
class SetHolidayProvider:
    """Holiday provider backed by an in-memory set of dates."""

    days: frozenset[date] = field(default_factory=frozenset)

    @classmethod
    def from_dates(cls, values: Iterable[DateInput]) -> SetHolidayProvider:
        """Build a provider from date-like values."""
        return cls(days=frozenset(coerce_date(value) for value in values))

    def is_holiday(self, day: date) -> bool:
        return day in self.days


@dataclass(frozen=True)
class HolidaysProvider:
    """Holiday provider backed by python-holidays."""

    country: str
    years: tuple[int, ...]
    subdivision: str | None = None
    observed: bool = True

    def __post_init__(self) -> None:
        if not self.years:
            raise CalendarRangeError("HolidaysProvider requires at least one configured year.")

    @cached_property
    def source(self) -> Mapping[date, str]:
        """Materialized holiday source cached for repeated lookups."""
        return holidays.country_holidays(
            self.country,
            subdiv=self.subdivision,
            years=list(self.years),
            observed=self.observed,
        )

    def is_holiday(self, day: date) -> bool:
        if day.year not in self.years:
            raise CalendarRangeError(
                f"Date {day.isoformat()} is outside configured holiday years {self.years!r}."
            )
        return day in self.source

    @classmethod
    def from_country(
        cls,
        country: str,
        *,
        years: int | Sequence[int],
        subdivision: str | None = None,
        observed: bool = True,
    ) -> HolidaysProvider:
        """Convenience constructor from country metadata."""
        return cls(
            country=country,
            years=coerce_years(years),
            subdivision=subdivision,
            observed=observed,
        )


@dataclass(frozen=True, slots=True)
class CompositeHolidayProvider:
    """Holiday provider that returns holidays when any child provider does."""

    providers: tuple[HolidayProvider, ...]

    def __post_init__(self) -> None:
        if not self.providers:
            object.__setattr__(self, "providers", ())

    def is_holiday(self, day: date) -> bool:
        return any(provider.is_holiday(day) for provider in self.providers)

    @classmethod
    def combine(
        cls,
        providers: Iterable[HolidayProvider | None],
    ) -> CompositeHolidayProvider | None:
        """Combine providers, returning `None` if no providers are given."""
        materialized = tuple(provider for provider in providers if provider is not None)
        if not materialized:
            return None
        return cls(providers=materialized)
