"""Load-case selection tests (CORE-7)."""

from __future__ import annotations

import pytest

from pemds.core.loadcase import LoadCase, LoadCaseSet


def test_empty_load_case_set_raises():
    with pytest.raises(ValueError, match="at least one load case"):
        LoadCaseSet([])


def test_unknown_kind_raises():
    with pytest.raises(ValueError, match="unknown load case kind"):
        LoadCase(name="x", pressure_pa=1.0, temperature_c=20.0, kind="moon")


def test_governing_is_highest_non_test():
    cases = LoadCaseSet(
        [
            LoadCase("operating", 1.0e6, 150.0),
            LoadCase("unused", 0.5e6, 20.0),
            LoadCase("test", 1.5e6, 20.0, kind="test"),
        ]
    )
    assert cases.governing_internal().name == "operating"
    assert cases.test_case().name == "test"
