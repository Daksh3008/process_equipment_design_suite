"""End-to-end pack and determinism tests (NFR-2, PV-1..PV-4)."""

from __future__ import annotations

import json

import pytest

from pemds.core.validation import ValidationError
from pemds.packs.pv import PressureVesselPack
from pemds.packs.pv.model import VesselInputs

_BASE = dict(  # noqa: C408 - keyword form reads better for a fixture
    tag="V-101",
    orientation="vertical",
    inside_diameter_mm=2000.0,
    tangent_to_tangent_mm=4000.0,
    material_key="SA-516-70",
    head_material_key="SA-516-70",
    head_type="ellipsoidal",
    design_pressure_mpa=1.0,
    design_temperature_c=150.0,
    corrosion_allowance_mm=3.0,
    mill_undertolerance_mm=0.3,
    joint_type="1",
    radiography="full",
    provided_shell_thickness_mm=16.0,
    provided_head_thickness_mm=16.0,
)


def _pack():
    return PressureVesselPack()


def test_vessel_end_to_end(ctx):
    tree = _pack().calculate(VesselInputs(**_BASE), ctx)
    by_symbol = {r.symbol: r for r in tree.roots}
    # shell: circ pressure thickness 7.278020 mm + 3 mm CA + 0.3 mm mill = 10.578020 mm
    assert by_symbol["t_shell"].value == pytest.approx(0.010578020378, rel=1e-9)
    assert by_symbol["t_shell"].verdict.value == "pass"
    # MAWP from as-built metal = 16 - 0.3 mill - 3 CA = 12.7 mm
    assert by_symbol["MAWP"].value == pytest.approx(
        138.0e6 * 0.0127 / (1.0 + 0.6 * 0.0127), rel=1e-9
    )
    assert by_symbol["MAWP"].governing_case == "shell (circumferential)"
    assert by_symbol["P_T"].value == pytest.approx(1.3 * by_symbol["MAWP"].value, rel=1e-12)
    assert tree.overall_verdict().value == "pass"


def test_all_nodes_carry_citations(ctx):
    tree = _pack().calculate(VesselInputs(**_BASE), ctx)
    for result in tree.flatten():
        assert result.citation.standard, result.symbol
        assert result.citation.edition, result.symbol
        assert result.citation.clause, result.symbol


def test_determinism(ctx):
    inputs = VesselInputs(**_BASE)
    first = json.dumps(_pack().calculate(inputs, ctx).to_dict(), sort_keys=True)
    second = json.dumps(_pack().calculate(inputs, ctx).to_dict(), sort_keys=True)
    assert first == second


def test_undersized_shell_fails(ctx):
    undersized = dict(_BASE, provided_shell_thickness_mm=10.0)
    tree = _pack().calculate(VesselInputs(**undersized), ctx)
    shell = next(r for r in tree.roots if r.symbol == "t_shell")
    assert shell.verdict.value == "fail"
    assert tree.overall_verdict().value == "fail"


def test_design_pressure_above_mawp_fails(ctx):
    over = dict(_BASE, provided_shell_thickness_mm=8.0)
    tree = _pack().calculate(VesselInputs(**over), ctx)
    mawp = next(r for r in tree.roots if r.symbol == "MAWP")
    assert mawp.verdict.value == "fail"


def test_validation_blocks_bad_flat_head(ctx):
    bad = dict(_BASE, head_type="flat", flat_head_factor_c=5.0)
    inputs = VesselInputs(**bad)
    pack = _pack()
    issues = pack.validate(inputs)
    assert any(i.severity.value == "error" for i in issues)
    with pytest.raises(ValidationError):
        pack.calculate(inputs, ctx)


def test_experimental_checks_are_flagged(ctx):
    from pemds.calc import external

    result = external.external_pressure_cylinder(2.0, 4.0, 0.012, 190.0e9, ctx.editions)
    assert result.verification.value == "experimental"
    assert any(i.severity.value == "warning" for i in result.issues)
    # Pa = 2 * A * E / (3 * (Do/t)) with A = 1.1/(Do/t)^2
    do_t = 2.0 / 0.012
    expected = 2.0 * (1.1 / do_t**2) * 190.0e9 / (3.0 * do_t)
    assert result.value == pytest.approx(expected, rel=1e-12)


def test_uw12_is_enforced_not_taken_as_a_free_number(ctx):
    strict = _pack().calculate(VesselInputs(**dict(_BASE, radiography="none")), ctx)
    full = _pack().calculate(VesselInputs(**_BASE), ctx)
    strict_shell = next(r for r in strict.roots if r.symbol == "t_shell")
    full_shell = next(r for r in full.roots if r.symbol == "t_shell")
    assert strict_shell.value > full_shell.value
    strict_mawp = next(r for r in strict.roots if r.symbol == "MAWP").value
    full_mawp = next(r for r in full.roots if r.symbol == "MAWP").value
    assert strict_mawp < full_mawp


def test_invalid_joint_type_is_rejected(ctx):
    with pytest.raises(ValueError, match="no UW-12 joint efficiency"):
        _pack().calculate(VesselInputs(**dict(_BASE, joint_type="9")), ctx)


def test_unverified_material_data_is_surfaced(ctx):
    tree = _pack().calculate(VesselInputs(**_BASE), ctx)
    messages = [issue.message for result in tree.flatten() for issue in result.issues]
    assert any("provisional" in message for message in messages)


def test_ug16_floor_raises_required_thickness(ctx):
    # Low pressure would otherwise require less than the 1.5 mm code minimum.
    low = dict(
        _BASE,
        design_pressure_mpa=0.05,
        corrosion_allowance_mm=0.0,
        mill_undertolerance_mm=0.0,
        provided_shell_thickness_mm=None,
        provided_head_thickness_mm=None,
    )
    tree = _pack().calculate(VesselInputs(**low), ctx)
    shell = next(r for r in tree.roots if r.symbol == "t_shell")
    assert shell.value == pytest.approx(0.0015)  # floored by UG-16


def test_provided_thickness_below_allowances_is_a_validation_error(ctx):
    bad = dict(_BASE, provided_shell_thickness_mm=3.0)  # CA 3.0 + mill 0.3
    inputs = VesselInputs(**bad)
    pack = _pack()
    assert any(i.severity.value == "error" for i in pack.validate(inputs))
    with pytest.raises(ValidationError):
        pack.calculate(inputs, ctx)


def test_unverified_data_downgrades_verification(ctx):
    tree = _pack().calculate(VesselInputs(**_BASE), ctx)
    shell = next(r for r in tree.roots if r.symbol == "t_shell")
    mawp_result = next(r for r in tree.roots if r.symbol == "MAWP")
    assert shell.verification.value == "experimental"
    assert mawp_result.verification.value == "experimental"


def test_weights_are_reported(ctx):
    tree = _pack().calculate(VesselInputs(**_BASE), ctx)
    by_symbol = {r.symbol: r for r in tree.roots}
    empty = by_symbol["W_empty"].value
    operating = by_symbol["W_operating"].value
    test_weight = by_symbol["W_test"].value
    assert empty is not None and empty > 0
    assert operating > empty
    assert test_weight >= operating  # test fill is water, not the process liquid
    assert by_symbol["z_cg"].value > 0


# --- PV-3 nozzle schedule + PV-1 support ------------------------------------

_NOZZLE = dict(  # noqa: C408
    tag="N1",
    outside_diameter_mm=219.1,
    provided_neck_thickness_mm=8.18,
    projection_mm=300.0,
    elevation_mm=800.0,
    azimuth_deg=0.0,
)


def test_nozzle_reinforcement_passes_for_a_makeup_connection(ctx):
    tree = _pack().calculate(VesselInputs(**dict(_BASE, nozzles=[_NOZZLE])), ctx)
    nozzle = next(r for r in tree.roots if r.symbol == "nozzle_N1")
    assert nozzle.verdict.value == "pass"
    # A_avail = A1 + A2 = 0.001476 (required) is exceeded by 0.003765 m^2.
    assert nozzle.value == pytest.approx(0.0037645883930131, rel=1e-3)
    assert nozzle.citation.clause == "UG-37"
    assert nozzle.verification.value == "experimental"
    assert {child.symbol for child in nozzle.children} == {"tn", "A", "A_avail"}


def test_nozzle_reinforcement_fails_when_the_neck_is_undersized(ctx):
    thin = dict(_NOZZLE, provided_neck_thickness_mm=2.0, projection_mm=80.0)
    tree = _pack().calculate(VesselInputs(**dict(_BASE, nozzles=[thin])), ctx)
    nozzle = next(r for r in tree.roots if r.symbol == "nozzle_N1")
    assert nozzle.verdict.value == "fail"
    assert nozzle.margin is not None and nozzle.margin < 0


def test_nozzle_elevation_outside_the_shell_is_a_validation_error(ctx):
    bad = VesselInputs(**dict(_BASE, nozzles=[dict(_NOZZLE, elevation_mm=5000.0)]))
    assert any(i.severity.value == "error" for i in _pack().validate(bad))


def test_nozzle_neck_thicker_than_half_the_od_is_a_validation_error(ctx):
    bad = VesselInputs(
        **dict(_BASE, nozzles=[dict(_NOZZLE, outside_diameter_mm=100.0, provided_neck_thickness_mm=60.0)])
    )
    assert any("bore" in i.message for i in _pack().validate(bad))


def test_blank_nozzle_tag_is_a_validation_error(ctx):
    bad = VesselInputs(**dict(_BASE, nozzles=[dict(_NOZZLE, tag="  ")]))
    assert any("blank" in i.message for i in _pack().validate(bad))


def test_skirt_height_must_be_positive(ctx):
    bad = VesselInputs(**dict(_BASE, support_type="skirt", support_height_mm=0.0))
    assert any(i.severity.value == "error" for i in _pack().validate(bad))


def test_skirt_on_a_horizontal_vessel_warns(ctx):
    bad = VesselInputs(
        **dict(_BASE, orientation="horizontal", support_type="skirt", support_height_mm=800.0)
    )
    issues = _pack().validate(bad)
    assert any(i.severity.value == "warning" for i in issues)


def test_nozzle_results_disclose_provenance_and_experimental_status(ctx):
    tree = _pack().calculate(VesselInputs(**dict(_BASE, nozzles=[_NOZZLE])), ctx)
    nozzle = next(r for r in tree.roots if r.symbol == "nozzle_N1")
    assert "provided_neck_thickness_mm" in nozzle.inputs_used
    assert "design_pressure_mpa" in nozzle.inputs_used
    tn = next(child for child in nozzle.children if child.symbol == "tn")
    area = next(child for child in nozzle.children if child.symbol == "A")
    assert any("plain cylinder" in issue.message for issue in tn.issues)
    assert any("area method" in issue.message for issue in area.issues)
    for child in nozzle.children:
        assert child.issues  # each experimental node discloses itself


def test_neck_calculation_rejects_invalid_inputs(ctx):
    from pemds.calc import openings

    with pytest.raises(ValueError):
        openings.nozzle_neck_thickness(1.0e6, 0.1, 138.0e6, 1.0, ctx.editions, corrosion_allowance_m=-0.001)
    with pytest.raises(ValueError):
        openings.nozzle_reinforcement_check(0.2, 0.007, 0.005, 0.005, 0.15, ctx.editions, weld_area_m2=-1.0)


def test_vessel_recalc_is_within_budget(ctx):
    import statistics
    import time

    pack = _pack()
    inputs = VesselInputs(**_BASE)
    pack.calculate(inputs, ctx)
    samples = []
    for _ in range(20):
        start = time.perf_counter()
        pack.calculate(inputs, ctx)
        samples.append(time.perf_counter() - start)
    assert statistics.median(samples) < 0.1  # NFR-1: live recalc < 100 ms

