"""Fluid property correlation and phase tests (CC-2, CC-3, CC-4, CC-10)."""

from __future__ import annotations

import CoolProp.CoolProp as CP
import pytest

from pemds.data.components import ComponentDB
from pemds.data.fluid_properties import (
    Phase,
    boiling_point,
    design_case,
    phase_at,
    phase_of,
    saturation_pressure,
)


def test_saturation_pressure_matches_published_water_value(editions):
    # Water at 25 degC: P_sat = 3.1699 kPa (standard steam-table value).
    result = saturation_pressure("Water", 25.0, editions)
    assert result.value == pytest.approx(3169.93, rel=1e-3)
    assert result.citation.standard == "CoolProp"


def test_saturation_pressure_above_critical_is_unavailable_with_reason(editions):
    result = saturation_pressure("Water", 400.0, editions)
    assert result.value is None
    assert result.issues and result.issues[0].severity.value == "warning"


def test_boiling_point_water_at_atmosphere(editions):
    result = boiling_point("Water", 101325.0, editions)
    assert result.value == pytest.approx(100.0, abs=0.1)


def test_phase_liquid_vapour_and_supercritical():
    assert phase_of("Water", 25.0, 101325.0) is Phase.LIQUID
    assert phase_of("Water", 150.0, 101325.0) is Phase.VAPOUR
    assert phase_of("Water", 400.0, 30e6) is Phase.SUPERCRITICAL


def test_phase_on_the_saturation_line_is_two_phase():
    # Derive an exactly saturated state, then confirm it reads as two-phase.
    t_sat = CP.PropsSI("T", "P", 101325.0, "Q", 0, "Water") - 273.15
    assert phase_of("Water", t_sat, 101325.0) is Phase.TWO_PHASE


def test_phase_at_returns_reportable_row(editions):
    result = phase_at("Water", 25.0, 101325.0, editions)
    assert "liquid" in result.formula
    assert "P_sat" in result.substitutions


def test_design_case_stamps_every_value(editions):
    db = ComponentDB.load_default()
    case = design_case("Water", 25.0, 101325.0, editions, db=db)
    assert case.phase is Phase.LIQUID
    density = case.properties["rho"]
    assert density.value == pytest.approx(997.05, rel=1e-3)
    assert "CoolProp" in density.substitutions["source"]
    assert "accuracy" in density.substitutions  # CC-10 surfaces accuracy limits
    basis = case.design_basis()
    assert basis["density_kg_m3"] == pytest.approx(997.05, rel=1e-3)
    assert basis["vapour_pressure_pa"] == pytest.approx(3169.93, rel=1e-3)
    assert basis["phase"] is Phase.LIQUID


def test_determinism_same_inputs_identical_result(editions):
    first = design_case("Methanol", 40.0, 500000.0, editions)
    second = design_case("Methanol", 40.0, 500000.0, editions)
    assert first.properties["rho"].value == second.properties["rho"].value


def test_design_case_handles_pressure_outside_saturation_envelope(editions):
    # 25 MPa exceeds water's critical pressure (22.06 MPa): the boiling point is
    # unavailable but the design case must not raise (audit finding 2).
    case = design_case("Water", 25.0, 25.0e6, editions)
    boiling = case.properties["T_b"]
    assert boiling.value is None
    assert any(issue.severity.value == "warning" for issue in boiling.issues)
    assert case.properties["rho"].value == pytest.approx(1000.0, rel=1e-2)
