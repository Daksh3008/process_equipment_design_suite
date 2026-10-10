"""Golden tests for vessel weights and centre of gravity (PV-4, UG-22)."""

from __future__ import annotations

import math

import pytest

from pemds.calc import weights


def test_shell_and_head_metal_mass(editions):
    result = weights.vessel_metal_mass(2.0, 4.0, 0.013, 0.0127, "ellipsoidal", 7850.0, editions)
    radius_outer = 1.0 + 0.013
    shell_volume = math.pi * (radius_outer**2 - 1.0) * 4.0
    head_volume = 1.084 * math.pi * radius_outer**2 * 0.0127
    assert result.value == pytest.approx(7850.0 * (shell_volume + 2.0 * head_volume), rel=1e-12)
    assert result.citation.clause == "UG-22"


def test_liquid_fill_with_flat_heads(editions):
    result = weights.liquid_fill_mass(2.0, 4.0, "flat", 1000.0, editions)
    assert result.value == pytest.approx(1000.0 * math.pi * 1.0**2 * 4.0, rel=1e-12)


def test_operating_weight_and_centre_of_gravity(editions):
    operating = weights.operating_weight(2000.0, 5000.0, editions)
    assert operating.value == pytest.approx(7000.0)
    cg = weights.centre_of_gravity_height(4.0, 0.5, editions)
    assert cg.value == pytest.approx((4.0 + 1.0) / 2.0, rel=1e-12)


def test_unknown_head_type_rejected(editions):
    with pytest.raises(ValueError, match="no surface factor"):
        weights.vessel_metal_mass(2.0, 4.0, 0.013, 0.0127, "dodecahedral", 7850.0, editions)