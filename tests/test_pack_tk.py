"""Storage-tank pack end-to-end tests (TK-1..TK-3, VAL-2)."""

from __future__ import annotations

import json

import pytest

from pemds.core.validation import ValidationError
from pemds.packs.tk import StorageTankPack
from pemds.packs.tk.model import StorageTankInputs

_BASE = dict(  # noqa: C408 - keyword form reads better for a fixture
    tag="TK-101",
    diameter_mm=10000.0,
    design_liquid_height_mm=12000.0,
    specific_gravity=1.0,
    design_temperature_c=60.0,
    material_key="SA-516-70",
    joint_efficiency=1.0,
    corrosion_allowance_mm=1.0,
    provided_shell_thickness_mm=8.0,
    roof_type="cone",
    roof_slope_ratio=0.1667,
    roof_live_load_kpa=1.2,
    roof_dead_load_kpa=0.5,
)


def _pack():
    return StorageTankPack()


def test_tank_shell_thickness_matches_one_foot_method(ctx):
    tree = _pack().calculate(StorageTankInputs(**_BASE), ctx)
    by_symbol = {r.symbol: r for r in tree.roots}
    # 4.9*10*(12-0.3)*1.0/(138*1.0) = 4.1543478 mm pressure + 1 mm CA = 5.1543478 mm
    assert by_symbol["t_shell"].value == pytest.approx(0.005154347826, rel=1e-9)
    assert by_symbol["t_shell"].verdict.value == "pass"
    assert by_symbol["t_shell"].citation.clause == "5.6 shell design"


def test_tank_roof_and_status_are_reported(ctx):
    tree = _pack().calculate(StorageTankInputs(**_BASE), ctx)
    by_symbol = {r.symbol: r for r in tree.roots}
    assert by_symbol["t_roof"].value > 0
    assert by_symbol["t_roof"].citation.standard == "API 650"
    assert by_symbol["status"].value is None
    assert by_symbol["status"].verification.value == "experimental"


def test_tank_results_are_experimental_everywhere(ctx):
    tree = _pack().calculate(StorageTankInputs(**_BASE), ctx)
    assert tree.flatten()  # non-empty
    for result in tree.flatten():
        assert result.verification.value == "experimental", result.symbol
    messages = [issue.message for result in tree.flatten() for issue in result.issues]
    assert any("EXPERIMENTAL" in message for message in messages)


def test_tank_undersized_shell_fails(ctx):
    tree = _pack().calculate(StorageTankInputs(**dict(_BASE, provided_shell_thickness_mm=3.0)), ctx)
    shell = next(r for r in tree.roots if r.symbol == "t_shell")
    assert shell.verdict.value == "fail"
    assert tree.overall_verdict().value == "fail"


def test_tank_opening_check_included_when_specified(ctx):
    with_opening = dict(_BASE, opening_outside_diameter_mm=508.0, opening_neck_thickness_mm=8.0)
    tree = _pack().calculate(StorageTankInputs(**with_opening), ctx)
    opening = next(r for r in tree.roots if r.symbol == "A_avail")
    assert opening.verdict.value == "pass"
    assert opening.citation.clause == "5.7 openings"
    assert opening.verification.value == "experimental"


def test_tank_validation_blocks_thin_provided_plate(ctx):
    bad = StorageTankInputs(**dict(_BASE, provided_shell_thickness_mm=0.5))
    assert any(i.severity.value == "error" for i in _pack().validate(bad))
    with pytest.raises(ValidationError):
        _pack().calculate(bad, ctx)


def test_tank_determinism(ctx):
    inputs = StorageTankInputs(**_BASE)
    first = json.dumps(_pack().calculate(inputs, ctx).to_dict(), sort_keys=True)
    second = json.dumps(_pack().calculate(inputs, ctx).to_dict(), sort_keys=True)
    assert first == second


def test_tank_dome_and_floating_roofs_size(ctx):
    dome = _pack().calculate(
        StorageTankInputs(**dict(_BASE, roof_type="dome", roof_rise_mm=1000.0)), ctx
    )
    floating = _pack().calculate(StorageTankInputs(**dict(_BASE, roof_type="floating")), ctx)
    for tree in (dome, floating):
        roof = next(r for r in tree.roots if r.symbol == "t_roof")
        assert roof.verification.value == "experimental"
        assert roof.issues  # every experimental result discloses its limitation


def test_tank_oversized_opening_without_neck_fails(ctx):
    large = dict(_BASE, opening_outside_diameter_mm=2500.0)
    tree = _pack().calculate(StorageTankInputs(**large), ctx)
    opening = next(r for r in tree.roots if r.symbol == "A_avail")
    assert opening.verdict.value == "fail"
    assert tree.overall_verdict().value == "fail"


def test_tank_negligible_pressure_shell_tracks_corrosion_allowance(ctx):
    # With a near-zero pressure requirement the shell collapses to CA on the floor.
    small = dict(_BASE, design_liquid_height_mm=1000.0, specific_gravity=0.5)
    tree = _pack().calculate(StorageTankInputs(**small), ctx)
    shell = next(r for r in tree.roots if r.symbol == "t_shell")
    t_mm = 4.9 * 10.0 * (1.0 - 0.3) * 0.5 / 138.0  # one-foot method yields millimetres
    assert shell.value == pytest.approx(t_mm * 1e-3 + 0.001, rel=1e-6)


def test_tank_courses_thin_towards_the_top(ctx):
    tree = _pack().calculate(StorageTankInputs(**_BASE), ctx)
    shell = next(r for r in tree.roots if r.symbol == "t_shell")
    courses = [c for c in shell.children if c.symbol.startswith("t_c")]
    # H=12 m, plate width 2.4 m -> 5 courses; bottom (full head) must be thickest.
    assert [c.symbol for c in courses] == ["t_c1", "t_c2", "t_c3", "t_c4", "t_c5"]
    thicknesses = [c.value for c in courses]
    assert thicknesses == sorted(thicknesses, reverse=True)
    assert thicknesses[0] > thicknesses[-1]
    # Each course reports the level and static pressure it can sustain.
    assert "max liquid level" in courses[0].substitutions
    assert "max static pressure" in courses[0].substitutions


def test_tank_plate_takeoff_counts_courses_and_plates(ctx):
    tree = _pack().calculate(StorageTankInputs(**_BASE), ctx)
    plates = next(r for r in tree.roots if r.symbol == "N_plates")
    # D=10 m -> circumference 31.42 m; 6 m plates -> 6 per course; H/w -> 5 courses.
    assert plates.value == 30.0
    children = {c.symbol: c.value for c in plates.children}
    assert children["N_courses"] == 5.0
    assert children["plates_per_course"] == 6.0
    assert children["stagger_offset"] == pytest.approx(3.0)  # half a plate length


def test_tank_plate_width_changes_the_course_count(ctx):
    fine = dict(_BASE, plate_width_mm=2000.0)  # 12 m / 2 m = 6 courses
    tree = _pack().calculate(StorageTankInputs(**fine), ctx)
    plates = next(r for r in tree.roots if r.symbol == "N_plates")
    assert next(c for c in plates.children if c.symbol == "N_courses").value == 6.0


def test_tank_roof_calculation_can_be_disabled(ctx):
    tree = _pack().calculate(StorageTankInputs(**dict(_BASE, include_roof_calculation=False)), ctx)
    assert not any(r.symbol == "t_roof" for r in tree.roots)
    assert any(r.symbol == "t_shell" for r in tree.roots)
    assert any(r.symbol == "N_plates" for r in tree.roots)
