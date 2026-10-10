"""Golden tests for stiffening rings (UG-29) — experimental."""

from __future__ import annotations

import pytest

from pemds.calc import rings
from pemds.calc.external import factor_a_elastic_cylinder


def _args() -> dict:
    return {
        "outside_diameter_m": 2.0,
        "ring_spacing_m": 1.0,
        "shell_thickness_m": 0.012,
        "ring_section_area_m2": 0.0004,
    }


def test_required_inertia_formula(editions):
    result = rings.stiffening_ring_check(**_args(), editions=editions)
    do_t = 2.0 / 0.012
    factor_a = factor_a_elastic_cylinder(do_t)
    effective_thickness = 0.012 + 0.0004 / 1.0
    expected = 2.0**2 * 1.0 * effective_thickness * factor_a / 14.0
    assert result.value == pytest.approx(expected, rel=1e-12)
    assert result.citation.clause == "UG-29"
    assert result.verification.value == "experimental"


def test_pass_and_fail_against_provided_inertia(editions):
    ample = rings.stiffening_ring_check(
        **_args(), editions=editions, provided_inertia_m4=1.0e-3
    )
    assert ample.verdict.value == "pass"
    insufficient = rings.stiffening_ring_check(
        **_args(), editions=editions, provided_inertia_m4=1.0e-12
    )
    assert insufficient.verdict.value == "fail"


def test_non_positive_provided_inertia_rejected(editions):
    with pytest.raises(ValueError, match="provided_inertia_m4 must be > 0"):
        rings.stiffening_ring_check(**_args(), editions=editions, provided_inertia_m4=0.0)