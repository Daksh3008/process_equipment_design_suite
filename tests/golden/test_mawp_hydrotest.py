"""Golden tests for minimums, MAWP and hydrotest (UG-16, UG-45, UG-98, UG-99)."""

from __future__ import annotations

import pytest

from pemds.calc import hydrotest, mawp, minimums


def test_ug16_minimum(editions):
    result = minimums.minimum_shell_thickness(editions)
    assert result.value == pytest.approx(0.0015)
    assert result.citation.clause == "UG-16(b)"


def test_ug45_connection_minimum(editions):
    result = minimums.connection_minimum_thickness(0.005, 0.010, 0.008, editions)
    assert result.value == pytest.approx(0.008)  # max(0.005, min(0.010, 0.008))
    assert result.citation.clause == "UG-45"


def test_governing_mawp_names_component(editions):
    result = mawp.governing_mawp({"shell": 2.0e6, "head": 1.5e6}, editions)
    assert result.value == pytest.approx(1.5e6)
    assert result.governing_case == "head"
    assert result.citation.clause == "UG-98"


def test_hydrotest_pressure(editions):
    result = hydrotest.hydrostatic_test_pressure(1.0e6, 110.0e6, 100.0e6, editions)
    assert result.value == pytest.approx(1.3 * 1.0e6 * 1.1, rel=1e-12)
    assert result.citation.clause == "UG-99(b)"


def test_empty_mawp_map_rejected(editions):
    with pytest.raises(ValueError, match="at least one component"):
        mawp.governing_mawp({}, editions)
