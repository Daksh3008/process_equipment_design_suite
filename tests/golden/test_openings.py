"""Golden tests for openings and reinforcement (UG-37) — experimental."""

from __future__ import annotations

import pytest

from pemds.calc import openings


def test_required_area(editions):
    result = openings.required_reinforcement_area(0.1, 0.008, editions)
    assert result.value == pytest.approx(0.1 * 0.008)
    assert result.verification.value == "experimental"
    assert result.citation.clause == "UG-37"


def test_reinforcement_fails_when_short(editions):
    result = openings.nozzle_reinforcement_check(0.1, 0.008, 0.002, 0.001, 0.05, editions)
    # available = 0.002*0.1 + 2*0.001*0.05 = 3e-4 m^2; required = 8e-4 m^2
    assert result.value == pytest.approx(3.0e-4)
    assert result.verdict.value == "fail"
    assert result.margin == pytest.approx((3.0e-4 - 8.0e-4) / 8.0e-4)


def test_reinforcement_passes_when_ample(editions):
    result = openings.nozzle_reinforcement_check(
        0.1, 0.008, 0.02, 0.01, 0.10, editions
    )
    assert result.verdict.value == "pass"
    assert result.margin > 0
