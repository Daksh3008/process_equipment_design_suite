"""Golden tests for UG-27 cylindrical shells.

The reference case is a shell at 250 psi, 30 in inside radius, 20 ksi allowable
stress, E = 1.0. Expected thicknesses are computed independently in imperial
units and converted, so an error in the implemented coefficient is caught.
"""

from __future__ import annotations

import pytest

from pemds.calc import shell

_PSI = 6894.757293168  # Pa per psi
_IN = 0.0254  # m per inch

P = 250.0 * _PSI
R = 30.0 * _IN
S = 20000.0 * _PSI
E = 1.0


def test_circumferential_thickness(editions):
    result = shell.circumferential_thickness(P, R, S, E, editions, 0.0)
    expected = (250.0 * 30.0 / (20000.0 - 0.6 * 250.0)) * _IN
    assert result.value == pytest.approx(expected, rel=1e-9)
    assert result.citation.clause == "UG-27(c)(1)"


def test_longitudinal_thickness(editions):
    result = shell.longitudinal_thickness(P, R, S, E, editions, 0.0)
    expected = (250.0 * 30.0 / (2.0 * 20000.0 + 0.4 * 250.0)) * _IN
    assert result.value == pytest.approx(expected, rel=1e-9)
    assert result.citation.clause == "UG-27(c)(2)"


def test_circumferential_mawp_inverts_thickness(editions):
    thickness = shell.circumferential_thickness(P, R, S, E, editions, 0.0).value
    mawp = shell.circumferential_mawp(thickness, R, S, E, editions)
    assert mawp.value == pytest.approx(P, rel=1e-12)


def test_longitudinal_mawp_inverts_thickness(editions):
    thickness = shell.longitudinal_thickness(P, R, S, E, editions, 0.0).value
    mawp = shell.longitudinal_mawp(thickness, R, S, E, editions)
    assert mawp.value == pytest.approx(P, rel=1e-12)


def test_corrosion_allowance_is_additive(editions):
    without = shell.circumferential_thickness(P, R, S, E, editions, 0.0).value
    with_ca = shell.circumferential_thickness(P, R, S, E, editions, 0.003).value
    assert with_ca - without == pytest.approx(0.003, rel=1e-12)


def test_non_physical_pressure_is_rejected(editions):
    with pytest.raises(ValueError, match="S\\*E > 0.6\\*P"):
        shell.circumferential_thickness(10.0e9, R, 1.0e6, 1.0, editions)
