"""Domain and integration exceptions."""


class BizcalError(Exception):
    """Base exception for the library."""


class ValidationError(BizcalError):
    """Raised when input data is structurally invalid."""


class CalendarConfigurationError(BizcalError):
    """Raised when calendar settings or builder configuration are invalid."""


class CalendarRangeError(BizcalError):
    """Raised when a holiday provider cannot resolve a requested range."""


class TimezoneError(BizcalError):
    """Raised when a timezone-aware operation receives invalid datetimes."""

