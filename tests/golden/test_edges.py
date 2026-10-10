"""Error-path and edge-case tests across the calc modules (code craft 7.3)."""

from __future__ import annotations

import math

import pytest

from pemds.calc import common, external, heads, mawp, minimums, openings, shell


def test_require_positive_rejects_nan():
    with pytest.raises(ValueError, match="must be finite"):
        common.require_positive(P=math.nan)


def test_require_positive_rejects_zero():
    with pytest.raises(ValueError, match="must be > 0"):
        common.require_positive(P=0.0)


def test_longitudinal_mawp_inversion_guard(editions):
    with pytest.raises(ValueError, match="R > 0.4\\*t"):
        shell.longitudinal_mawp(1.0, 0.1, 100.0e6, 1.0, editions)


def test_ellipsoidal_non_physical_pressure(editions):
    with pytest.raises(ValueError, match="2\\*S\\*E > 0.2\\*P"):
        heads.ellipsoidal_thickness(20.0e6, 2.0, 1.0e6, 1.0, editions)


def test_hemispherical_mawp_inverts(editions):
    thickness = heads.hemispherical_thickness(1.0e6, 1.0, 100.0e6, 1.0, editions, 0.0).value
    mawp = heads.hemispherical_mawp(thickness, 1.0, 100.0e6, 1.0, editions)
    assert mawp.value == pytest.approx(1.0e6, rel=1e-12)


def test_external_pressure_thick_wall_rejected(editions):
    with pytest.raises(ValueError, match="Do/t >= 10"):
        external.external_pressure_cylinder(1.0, 1.0, 0.2, 190.0e9, editions)


def test_openings_negative_excess_rejected(editions):
    with pytest.raises(ValueError, match="must be >= 0"):
        openings.nozzle_reinforcement_check(0.1, 0.008, -0.001, 0.001, 0.05, editions)


def test_minimums_negative_tc_rejected(editions):
    with pytest.raises(ValueError, match="tc_m must be >= 0"):
        minimums.connection_minimum_thickness(0.005, 0.010, -0.001, editions)


def test_mawp_non_positive_component_rejected(editions):
    with pytest.raises(ValueError, match="must be finite and > 0"):
        mawp.governing_mawp({"shell": 0.0}, editions)


def test_mawp_non_finite_component_rejected(editions):
    with pytest.raises(ValueError, match="must be finite and > 0"):
        mawp.governing_mawp({"shell": float("nan")}, editions)


def test_corrosion_allowance_negative_rejected(editions):
    with pytest.raises(ValueError, match="must be >= 0"):
        shell.circumferential_thickness(1.0e6, 1.0, 100.0e6, 1.0, editions, -0.001)
