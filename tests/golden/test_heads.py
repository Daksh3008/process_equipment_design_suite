"""Golden tests for UG-32 formed heads and UG-34 flat heads."""

from __future__ import annotations

import math

import pytest

from pemds.calc import flat, heads


def test_ellipsoidal_thickness(editions):
    result = heads.ellipsoidal_thickness(1.0e6, 2.0, 100.0e6, 1.0, editions, 0.0)
    assert result.value == pytest.approx(2.0e6 / 199.8e6, rel=1e-12)
    assert result.citation.clause == "UG-32(c)"


def test_torispherical_thickness(editions):
    result = heads.torispherical_thickness(1.0e6, 2.0, 100.0e6, 1.0, editions, 0.0)
    assert result.value == pytest.approx(0.885 * 1.0e6 * 2.0 / 99.9e6, rel=1e-12)
    assert result.citation.clause == "UG-32(d)"


def test_hemispherical_thickness(editions):
    result = heads.hemispherical_thickness(1.0e6, 1.0, 100.0e6, 1.0, editions, 0.0)
    assert result.value == pytest.approx(1.0e6 / 199.8e6, rel=1e-12)
    assert result.citation.clause == "UG-32(e)"


def test_conical_thickness(editions):
    result = heads.conical_thickness(1.0e6, 2.0, 30.0, 100.0e6, 1.0, editions, 0.0)
    expected = 2.0e6 / (2.0 * math.cos(math.radians(30.0)) * 99.4e6)
    assert result.value == pytest.approx(expected, rel=1e-12)
    assert result.citation.clause == "UG-32(f)"


def test_ellipsoidal_mawp_inverts_thickness(editions):
    thickness = heads.ellipsoidal_thickness(1.0e6, 2.0, 100.0e6, 1.0, editions, 0.0).value
    mawp = heads.ellipsoidal_mawp(thickness, 2.0, 100.0e6, 1.0, editions)
    assert mawp.value == pytest.approx(1.0e6, rel=1e-12)


def test_torispherical_mawp_inverts_thickness(editions):
    thickness = heads.torispherical_thickness(1.0e6, 2.0, 100.0e6, 1.0, editions, 0.0).value
    mawp = heads.torispherical_mawp(thickness, 2.0, 100.0e6, 1.0, editions)
    assert mawp.value == pytest.approx(1.0e6, rel=1e-12)


def test_flat_head_thickness(editions):
    result = flat.flat_head_thickness(1.0e6, 1.0, 0.33, 100.0e6, 1.0, editions, 0.0)
    assert result.value == pytest.approx((0.33 * 1.0e6 / 100.0e6) ** 0.5, rel=1e-12)
    assert result.citation.clause == "UG-34(c)(2)"


def test_flat_head_mawp_inverts_thickness(editions):
    thickness = flat.flat_head_thickness(1.0e6, 1.0, 0.33, 100.0e6, 1.0, editions, 0.0).value
    mawp = flat.flat_head_mawp(thickness, 1.0, 0.33, 100.0e6, 1.0, editions)
    assert mawp.value == pytest.approx(1.0e6, rel=1e-12)


def test_conical_angle_out_of_range_rejected(editions):
    with pytest.raises(ValueError, match="half-apex angle"):
        heads.conical_thickness(1.0e6, 2.0, 45.0, 100.0e6, 1.0, editions)
