"""Golden tests for the B16.5 flange calcs (FL-1..FL-3).

The rating and bolting numbers are hand-checks against the demonstration data
set in ``src/pemds/data/tables``; they are regression anchors, not verified
standard values. The bolt target torque is checked against the published
torque-preload relation ``T = K * D * F`` using an independent hand calculation
(specification section 7: primary acceptance is independent hand calculation).
"""

from __future__ import annotations

import math

import pytest

from pemds.calc import flange


def test_rating_values_match_the_transcribed_steps(editions):
    # group 1.1 (carbon steel), Class 300 at 100 degC
    carbon = flange.pressure_temp_rating("2", "1.1", 300, 100.0, editions)
    assert carbon.value == pytest.approx(5.10e6, rel=1e-12)
    # group 2.2 (austenitic), Class 600 at 200 degC
    austenitic = flange.pressure_temp_rating("2", "2.2", 600, 200.0, editions)
    assert austenitic.value == pytest.approx(8.55e6, rel=1e-12)
    assert carbon.citation.clause == austenitic.citation.clause


def test_step_lookup_uses_the_next_higher_temperature(editions):
    # At 250 degC the next tabulated step is 300 degC (1.38 MPa), not an interpolated value.
    result = flange.pressure_temp_rating("2", "1.1", 150, 250.0, editions)
    assert result.value == pytest.approx(1.38e6, rel=1e-12)


def test_select_class_is_lowest_and_has_a_negative_margin_when_failing(editions):
    passing = flange.select_class("2", "1.1", 2.0e6, 100.0, editions)
    assert int(passing.value) == 300
    assert passing.margin == pytest.approx((5.10e6 - 2.0e6) / 2.0e6, rel=1e-12)
    failing = flange.select_class("2", "1.1", 20.0e6, 100.0, editions)
    assert failing.verdict.value == "fail"


def test_target_torque_hand_benchmark(editions):
    # T = K*D*(W/n); W = max(Wm1, Wm2) from the App. 2 load form.
    pressure = 2.0e6
    mean_diameter = 0.1
    effective_width = 0.00225
    m_factor = 3.0
    y_factor = 69.0e6
    bolt_count = 4
    bolt_diameter = 0.015875
    bolt_area = 145.8e-6
    allowable = 138.0e6
    nut_factor = 0.2

    result = flange.bolt_up_check(
        pressure,
        mean_diameter,
        effective_width,
        m_factor,
        y_factor,
        bolt_count,
        bolt_area,
        bolt_diameter,
        allowable,
        nut_factor,
        editions,
    )

    hydrostatic = math.pi / 4.0 * mean_diameter**2 * pressure
    gasket_operating = 2.0 * effective_width * math.pi * mean_diameter * m_factor * pressure
    operating = hydrostatic + gasket_operating
    seating = math.pi * effective_width * mean_diameter * y_factor
    target_load = max(operating, seating)
    expected_torque = nut_factor * bolt_diameter * (target_load / bolt_count)

    torque = next(child for child in result.children if child.symbol == "T_bolt")
    assert torque.value == pytest.approx(expected_torque, rel=1e-12)
    # Seating governs this case, so the seating load sets the target torque.
    assert seating > operating
    assert result.substitutions["governing load"] == "seating"


def test_bolt_area_margin_sign_matches_verdict(editions):
    result = flange.bolt_up_check(
        2.0e6, 0.1, 0.00225, 3.0, 69.0e6, 4, 145.8e-6, 0.015875, 138.0e6, 0.2, editions
    )
    assert result.verdict.value == "pass"
    assert result.margin is not None and result.margin > 0


def test_mating_pair_is_experimental_and_carries_a_pair(editions):
    result = flange.mating_flange_pair("4", 300, "raised_face", "spiral-wound", 8, 19.05, editions)
    assert result.value == pytest.approx(2.0)
    assert result.verification.value == "experimental"
    assert any(issue.severity.value == "warning" for issue in result.issues)
