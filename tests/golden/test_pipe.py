"""Golden tests for B31.3 pipe calcs (304.1.2)."""

from __future__ import annotations

import pytest

from pemds.calc import pipe


def test_straight_pipe_thickness(editions):
    result = pipe.straight_pipe_thickness(
        10.0e6, 0.2, 100.0e6, 1.0, 0.4, editions, corrosion_allowance_m=0.003, mill_tolerance_pct=12.5
    )
    pressure_t = 10.0e6 * 0.2 / (2.0 * (100.0e6 + 10.0e6 * 0.4))
    expected = (pressure_t + 0.003) / (1.0 - 0.125)
    assert result.children[0].value == pytest.approx(pressure_t, rel=1e-12)
    assert result.value == pytest.approx(expected, rel=1e-12)
    assert result.citation.clause == "304.1.2"


def test_pipe_mawp_inverts_thickness(editions):
    thickness = pipe.straight_pipe_thickness(10.0e6, 0.2, 100.0e6, 1.0, 0.4, editions).children[0].value
    mawp = pipe.pipe_mawp(thickness, 0.2, 100.0e6, 1.0, 0.4, editions)
    assert mawp.value == pytest.approx(10.0e6, rel=1e-12)
    assert mawp.citation.clause == "304.1.2"


def test_pipe_mawp_inversion_guard(editions):
    with pytest.raises(ValueError, match="D > 2\\*Y\\*t"):
        pipe.pipe_mawp(1.0, 0.1, 100.0e6, 1.0, 0.4, editions)


def test_branch_check_is_experimental(editions):
    result = pipe.branch_reinforcement_check(0.06, 0.001, 0.002, 0.001, editions)
    assert result.verification.value == "experimental"
    assert result.citation.clause == "304.3"