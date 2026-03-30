from __future__ import annotations

from datetime import time

import pytest

from django_bizcal.exceptions import ValidationError
from django_bizcal.windows import (
    TimeWindow,
    build_time_windows,
    intersect_time_windows,
    normalize_time_windows,
    subtract_time_windows,
)


def test_time_window_validates_start_before_end() -> None:
    with pytest.raises(ValidationError):
        TimeWindow.from_pair("18:00", "09:00")


def test_normalize_time_windows_merges_overlapping_and_adjacent_windows() -> None:
    windows = build_time_windows(
        [
            ("09:00", "11:00"),
            ("10:30", "12:00"),
            ("12:00", "13:00"),
        ]
    )
    assert windows == (TimeWindow(time(9, 0), time(13, 0)),)


def test_intersect_time_windows_returns_only_overlaps() -> None:
    left = normalize_time_windows([TimeWindow.from_pair("09:00", "13:00")])
    right = normalize_time_windows(
        [
            TimeWindow.from_pair("08:00", "10:00"),
            TimeWindow.from_pair("11:00", "14:00"),
        ]
    )
    assert intersect_time_windows(left, right) == (
        TimeWindow.from_pair("09:00", "10:00"),
        TimeWindow.from_pair("11:00", "13:00"),
    )


def test_subtract_time_windows_splits_remaining_segments() -> None:
    base = [TimeWindow.from_pair("09:00", "18:00")]
    blockers = [
        TimeWindow.from_pair("11:00", "12:00"),
        TimeWindow.from_pair("14:00", "16:00"),
    ]
    assert subtract_time_windows(base, blockers) == (
        TimeWindow.from_pair("09:00", "11:00"),
        TimeWindow.from_pair("12:00", "14:00"),
        TimeWindow.from_pair("16:00", "18:00"),
    )

