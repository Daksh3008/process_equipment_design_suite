"""Golden tests for pump calcs (PU-2..PU-9).

Expected values are independent hand calculations from the published relation
and are compared numerically with a tight tolerance; no standard text is copied.
Hydraulic power is the worked example "water, 998 kg/m^3, 50 m^3/h at 60 m" and
the bearing life is the ISO 281 rating-life relation.
"""

from __future__ import annotations

import math

import pytest

from pemds.calc import pump
from pemds.core.provenance import VerificationStatus


def test_specific_speed_definition(editions):
    result = pump.specific_speed(3600.0, 0.02, 60.0, editions)
    assert result.value == pytest.approx(3600.0 * math.sqrt(0.02) / 60.0**0.75, rel=1e-12)
    assert result.citation.clause == "specific speed / type classification"


def test_suction_specific_speed_definition(editions):
    result = pump.suction_specific_speed(3600.0, 0.02, 3.0, editions)
    assert result.value == pytest.approx(3600.0 * math.sqrt(0.02) / 3.0**0.75, rel=1e-12)


def test_type_classification_ranges(editions):
    radial = pump.pump_type_classification(20.0, 150.0, 0.02, editions)
    mixed = pump.pump_type_classification(90.0, 150.0, 0.2, editions)
    axial = pump.pump_type_classification(180.0, 150.0, 0.9, editions)
    assert radial.substitutions["impeller family"] == "radial"
    assert mixed.substitutions["impeller family"] == "mixed-flow"
    assert axial.substitutions["impeller family"] == "axial"
    assert radial.verification is VerificationStatus.EXPERIMENTAL


def test_hydraulic_power_worked_example(editions):
    # P_hyd = rho*g*Q*H = 998 * 9.80665 * (50/3600) * 60 = 8 155.86 W.
    result = pump.hydraulic_power(998.0, 50.0 / 3600.0, 60.0, editions)
    assert result.value == pytest.approx(8155.863916666, rel=1e-12)


def test_absorbed_power_and_driver(editions):
    hydraulic = pump.hydraulic_power(998.0, 50.0 / 3600.0, 60.0, editions)
    absorbed = pump.absorbed_power(hydraulic.value, 0.73, editions)
    assert absorbed.value == pytest.approx(hydraulic.value / 0.73, rel=1e-12)
    driver = pump.motor_sizing(absorbed.value, editions, 1.15)
    assert driver.value == pytest.approx(15000.0, rel=1e-12)


def test_motor_current_definition(editions):
    current = pump.motor_current(11000.0, 400.0, 0.86, 3, editions)
    assert current.value == pytest.approx(11000.0 / (math.sqrt(3.0) * 400.0 * 0.86), rel=1e-12)


def test_shaft_torque_definition(editions):
    omega = pump.angular_speed_rad_s(3600.0)
    assert omega == pytest.approx(2.0 * math.pi * 60.0, rel=1e-12)
    torque = pump.shaft_torque(11172.416, omega, editions)
    assert torque.value == pytest.approx(11172.416 / omega, rel=1e-12)


def test_shaft_deflection_definition(editions):
    # Simply supported, central load: delta = F*L^3/(48*E*I).
    inertia = math.pi * 0.03**4 / 64.0
    result = pump.seal_chamber_deflection(500.0, 0.1, 0.1, 200.0e9, inertia, editions)
    expected = 500.0 * 0.2**3 / (48.0 * 200.0e9 * inertia)
    assert result.value == pytest.approx(expected, rel=1e-12)
    assert result.verdict.value == "pass"


def test_combined_shaft_stress_definition(editions):
    result = pump.combined_shaft_stress(25.0, 29.6358, 0.03, editions)
    section = math.pi * 0.03**3
    sigma_b = 32.0 * 25.0 / section
    tau = 16.0 * 29.6358 / section
    assert result.value == pytest.approx(math.sqrt(sigma_b**2 + 3.0 * tau**2), rel=1e-12)


def test_bearing_life_definition(editions):
    result = pump.bearing_life(80000.0, 4000.0, 3600.0, editions, exponent=3.0)
    expected = (1.0e6 / (60.0 * 3600.0)) * (80000.0 / 4000.0) ** 3
    assert result.value == pytest.approx(expected, rel=1e-12)
    assert result.citation.standard == "ISO 281"


def test_npsh_margin_definition(editions):
    result = pump.npsh_check(6.0, 2.8, editions, margin_m=0.6)
    assert result.verdict.value == "pass"
    assert result.margin == pytest.approx((6.0 - 3.4) / 3.4, rel=1e-12)
    failing = pump.npsh_check(3.0, 2.8, editions, margin_m=0.6)
    assert failing.verdict.value == "fail"


def test_casing_thickness_matches_ug27(editions):
    result = pump.casing_wall_thickness(2.0e6, 0.15, 138.0e6, 1.0, editions)
    expected = 2.0e6 * 0.15 / (138.0e6 - 0.6 * 2.0e6)
    assert result.value == pytest.approx(expected, rel=1e-12)
    mawp = pump.casing_mawp(expected, 0.15, 138.0e6, 1.0, editions)
    assert mawp.value == pytest.approx(2.0e6, rel=1e-12)
    test = pump.casing_hydrotest_pressure(mawp.value, editions)
    assert test.value == pytest.approx(1.5 * 2.0e6, rel=1e-12)


def test_operating_region_bands(editions):
    assert pump.operating_region_check(85.0, editions).verdict.value == "pass"
    assert pump.operating_region_check(60.0, editions).verdict.value == "warn"
    assert pump.operating_region_check(40.0, editions).verdict.value == "fail"


def test_vibration_limit_definition(editions):
    assert pump.vibration_check(0.002, editions).verdict.value == "pass"
    assert pump.vibration_check(0.005, editions).verdict.value == "fail"


def test_catalogue_interpolation_and_selection(ctx):
    from pemds.data.loader import load_package_data

    data = load_package_data("pumps/sample_curves.json")
    catalogue = pump.catalogue_from_data(data.data)
    best = pump.rank_candidates(50.0 / 3600.0, 60.0, catalogue, 3600.0)[0]
    assert best.model == "PU-SAMPLE-OH2"
    assert best.percent_bep == pytest.approx(50.0 / 60.0 * 100.0, rel=1e-12)
    assert best.npshr_m == pytest.approx(2.8, rel=1e-12)
    assert best.efficiency_pct == pytest.approx(73.0, rel=1e-12)
    selection = pump.select_from_catalogue(50.0 / 3600.0, 60.0, catalogue, ctx.editions, 3600.0)
    assert selection.verification is VerificationStatus.EXPERIMENTAL
    assert selection.citation.clause == "catalogue selection (generic sample curves)"
