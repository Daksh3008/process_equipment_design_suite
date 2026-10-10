"""Unit-handling tests (NFR-3)."""

from __future__ import annotations

import pytest

from pemds.core.units import UnitSystem, convert, from_base, to_base


def test_length_round_trip():
    assert to_base(1.0, "in", "length") == pytest.approx(0.0254, rel=1e-12)
    assert from_base(0.0254, "length", UnitSystem.IMPERIAL) == pytest.approx(1.0, rel=1e-12)


def test_pressure_display():
    assert from_base(1.0e6, "pressure", UnitSystem.SI) == pytest.approx(1.0, rel=1e-12)
    assert from_base(1.0e6, "pressure", UnitSystem.IMPERIAL) == pytest.approx(145.0377, rel=1e-4)


def test_temperature_offset():
    assert convert(0.0, "degC", "degF") == pytest.approx(32.0, rel=1e-12)
    assert to_base(212.0, "degF", "temperature") == pytest.approx(100.0, rel=1e-9)


def test_stress_imperial():
    # 20 ksi = 137.8952 MPa
    assert to_base(20.0, "ksi", "stress") == pytest.approx(137.8952e6, rel=1e-6)
