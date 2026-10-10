"""Component-driven design case wired into the pressure-vessel pack (CC-3, CC-4)."""

from __future__ import annotations

import pytest

from pemds.core.validation import ValidationError
from pemds.packs.pv import PressureVesselPack
from pemds.packs.pv.model import VesselInputs

_KWARGS = {
    "tag": "V-201",
    "inside_diameter_mm": 2000.0,
    "tangent_to_tangent_mm": 4000.0,
    "material_key": "SA-516-70",
    "head_material_key": "SA-516-70",
    "design_pressure_mpa": 1.0,
    "design_temperature_c": 80.0,
}


def test_component_key_adds_a_fluid_design_case(ctx):
    tree = PressureVesselPack().calculate(
        VesselInputs(**_KWARGS, fluid_component_key="Water"), ctx
    )
    fluid = next(r for r in tree.roots if r.symbol == "fluid")
    # Water near 80 degC / 1 MPa: ~971.8 kg/m3.
    assert fluid.value == pytest.approx(971.8, rel=5e-3)
    assert fluid.substitutions["phase"] == "liquid"
    assert {c.symbol for c in fluid.children} >= {"rho", "P_sat", "mu_L"}


def test_component_density_drives_the_weight_calculation(ctx):
    manual = PressureVesselPack().calculate(
        VesselInputs(**_KWARGS, liquid_density_kg_m3=1000.0), ctx
    )
    component = PressureVesselPack().calculate(
        VesselInputs(**_KWARGS, fluid_component_key="Water", liquid_density_kg_m3=1000.0), ctx
    )
    manual_liquid = next(r for r in manual.roots if r.symbol == "W_liquid")
    component_liquid = next(r for r in component.roots if r.symbol == "W_liquid")
    assert component_liquid.value < manual_liquid.value  # 971.8 < 1000


def test_unknown_component_is_reported_by_validation():
    inputs = VesselInputs(**_KWARGS, fluid_component_key="Unobtainium")
    issues = PressureVesselPack().validate(inputs)
    assert any(i.field == "fluid_component_key" for i in issues)


def test_unknown_component_blocks_calculation(ctx):
    inputs = VesselInputs(**_KWARGS, fluid_component_key="Unobtainium")
    with pytest.raises(ValidationError):
        PressureVesselPack().calculate(inputs, ctx)


def test_no_component_key_keeps_manual_density(ctx):
    tree = PressureVesselPack().calculate(VesselInputs(**_KWARGS), ctx)
    assert not any(r.symbol == "fluid" for r in tree.roots)
    assert tree.overall_verdict().value == "pass"
