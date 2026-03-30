from __future__ import annotations

from importlib import resources


def test_package_marks_itself_as_typed() -> None:
    marker = resources.files("django_bizcal").joinpath("py.typed")
    assert marker.is_file()

