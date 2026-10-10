"""Load-case manager integration into the vessel pack (CORE-7, UG-22)."""

from __future__ import annotations

from pemds.core.validation import ValidationError
from pemds.packs.pv import PressureVesselPack
from pemds.packs.pv.model import VesselInputs

_KWARGS = {
    "tag": "V-301",
    "inside_diameter_mm": 2000.0,
    "tangent_to_tangent_mm": 4000.0,
    "material_key": "SA-516-70",
    "head_material_key": "SA-516-70",
    "design_pressure_mpa": 1.0,
    "design_temperature_c": 150.0,
}


def test_governing_non_test_case_drives_design(ctx):
    cases = [
        {"name": "operating", "kind": "operating", "pressure_mpa": 1.2, "temperature_c": 150.0},
        {"name": "startup", "kind": "unused", "pressure_mpa": 0.8, "temperature_c": 40.0},
        {"name": "hydro", "kind": "test", "pressure_mpa": 2.0, "temperature_c": 20.0},
    ]
    tree = PressureVesselPack().calculate(VesselInputs(**_KWARGS, load_cases=cases), ctx)
    assert tree.governing_case == "operating"


def test_highest_pressure_non_test_case_wins(ctx):
    cases = [
        {"name": "operating", "kind": "operating", "pressure_mpa": 1.0, "temperature_c": 120.0},
        {"name": "upset", "kind": "maintenance", "pressure_mpa": 1.6, "temperature_c": 90.0},
    ]
    tree = PressureVesselPack().calculate(VesselInputs(**_KWARGS, load_cases=cases), ctx)
    assert tree.governing_case == "upset"
    # The thicker shell required by the governing case must exceed the design-only run.
    plain = PressureVesselPack().calculate(VesselInputs(**_KWARGS), ctx)
    governed_shell = next(r for r in tree.roots if r.symbol == "t_shell")
    plain_shell = next(r for r in plain.roots if r.symbol == "t_shell")
    assert governed_shell.value > plain_shell.value


def test_test_case_only_is_rejected():
    cases = [{"name": "hydro", "kind": "test", "pressure_mpa": 2.0, "temperature_c": 20.0}]
    issues = PressureVesselPack().validate(VesselInputs(**_KWARGS, load_cases=cases))
    assert any(issue.field == "load_cases" for issue in issues)


def test_test_only_case_blocks_calculation(ctx):
    cases = [{"name": "hydro", "kind": "test", "pressure_mpa": 2.0, "temperature_c": 20.0}]
    try:
        PressureVesselPack().calculate(VesselInputs(**_KWARGS, load_cases=cases), ctx)
    except ValidationError:
        pass
    else:  # pragma: no cover - the call must raise
        raise AssertionError("expected ValidationError for a test-only load-case set")
