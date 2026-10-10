"""Pump pack end-to-end tests (FR-PU, PU-1..PU-15)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError as PydanticValidationError

from pemds.core.provenance import VerificationStatus
from pemds.core.validation import ValidationError
from pemds.packs.pu import PumpPack
from pemds.packs.pu.datasheet import pump_datasheet_rows
from pemds.packs.pu.drawing import pump_ga_from, write_dxf, write_pdf
from pemds.packs.pu.model import PumpInputs

_KWARGS = dict(  # noqa: C408 - keyword form reads better for a fixture
    tag="P-101",
    service="process water",
    fluid_name="water",
    flow_m3_h=50.0,
    head_m=60.0,
    density_kg_m3=998.0,
    viscosity_cp=1.0,
    vapour_pressure_kpa=2.3,
    temperature_c=25.0,
    npsh_available_m=6.0,
    design_pressure_mpa=2.0,
    casing_material_key="SA-516-70",
    casing_inside_radius_mm=150.0,
    corrosion_allowance_mm=3.0,
    joint_efficiency=1.0,
    provided_casing_thickness_mm=20.0,
    shaft_diameter_mm=30.0,
    shaft_bearing_span_mm=200.0,
    shaft_load_offset_mm=100.0,
    shaft_radial_load_n=500.0,
    seal_chamber_pressure_mpa=1.5,
    seal_chamber_inside_radius_mm=40.0,
    seal_chamber_deflection_limit_mm=0.05,
    seal_hazardous=False,
    seal_solids=False,
    bearing_type="ball",
    radial_bearing_dynamic_load_n=80000.0,
    radial_bearing_load_n=4000.0,
    min_bearing_life_h=25000.0,
    motor_margin=1.15,
    motor_voltage_v=400.0,
    motor_power_factor=0.86,
    motor_phases=3,
    chloride_ppm=0.0,
    h2s_present=False,
    vibration_velocity_mm_s=2.0,
)

_LOADS = [
    dict(  # noqa: C408
        tag="S1",
        service="suction",
        size_mm=150.0,
        force_x_n=2000.0,
        moment_y_nm=1000.0,
        allowable_force_n=4000.0,
        allowable_moment_nm=3000.0,
    ),
    dict(  # noqa: C408
        tag="D1",
        service="discharge",
        size_mm=100.0,
        force_x_n=5000.0,
        moment_z_nm=4000.0,
        allowable_force_n=4000.0,
        allowable_moment_nm=3000.0,
    ),
]


def _pack():
    return PumpPack()


def _tree(ctx, **overrides):
    return _pack().calculate(PumpInputs(**{**_KWARGS, **overrides}), ctx)


def _by_symbol(tree):
    return {result.symbol: result for result in tree.roots}


def test_pump_end_to_end(ctx):
    tree = _tree(ctx)
    by_symbol = _by_symbol(tree)
    flow = 50.0 / 3600.0
    expected_ns = 3600.0 * flow**0.5 / 60.0**0.75
    assert by_symbol["Ns"].value == pytest.approx(expected_ns, rel=1e-12)
    assert by_symbol["selection"].value == pytest.approx(73.0, rel=1e-9)
    assert by_symbol["selection"].substitutions["model"] == "PU-SAMPLE-OH2"
    assert by_symbol["%BEP"].value == pytest.approx(50.0 / 60.0 * 100.0, rel=1e-12)
    assert by_symbol["%BEP"].verdict.value == "pass"
    assert by_symbol["NPSHa"].verdict.value == "pass"
    assert tree.overall_verdict().value == "pass"


def test_all_nodes_carry_citations(ctx):
    tree = _tree(ctx)
    for result in tree.flatten():
        assert result.citation.standard, result.symbol
        assert result.citation.edition, result.symbol
        assert result.citation.clause, result.symbol


def test_determinism(ctx):
    inputs = PumpInputs(**_KWARGS)
    first = json.dumps(_pack().calculate(inputs, ctx).to_dict(), sort_keys=True)
    second = json.dumps(_pack().calculate(inputs, ctx).to_dict(), sort_keys=True)
    assert first == second


def test_hydraulic_and_absorbed_power(ctx):
    tree = _tree(ctx)
    by_symbol = _by_symbol(tree)
    flow = 50.0 / 3600.0
    expected_hyd = 998.0 * 9.80665 * flow * 60.0
    assert by_symbol["P_hyd"].value == pytest.approx(expected_hyd, rel=1e-12)
    assert by_symbol["P_abs"].value == pytest.approx(expected_hyd / 0.73, rel=1e-12)
    # 11.17 kW absorbed * 1.15 = 12.85 kW -> the next standard motor is 15 kW.
    assert by_symbol["P_motor"].value == pytest.approx(15000.0, rel=1e-12)


def test_motor_current_three_phase(ctx):
    tree = _tree(ctx)
    current = _by_symbol(tree)["I_motor"]
    absorbed = _by_symbol(tree)["P_abs"].value
    expected = absorbed / (1.7320508075688772 * 400.0 * 0.86)
    assert current.value == pytest.approx(expected, rel=1e-12)


def test_amp_check_uses_fla_when_supplied(ctx):
    tree = _tree(ctx, motor_fla_a=25.0)
    current = _by_symbol(tree)["I_motor"]
    assert current.verification is VerificationStatus.EXPERIMENTAL
    assert current.verdict.value == "pass"
    assert current.margin is not None and current.margin > 0


def test_catalogue_dependent_results_are_experimental(ctx):
    tree = _tree(ctx)
    by_symbol = _by_symbol(tree)
    # Hydraulic relations are verified engineering.
    for symbol in ("Ns", "Nss", "P_hyd", "M_shaft", "L10h", "v_rms"):
        assert by_symbol[symbol].verification is VerificationStatus.VERIFIED, symbol
    # Catalogue-derived results are experimental and disclose why.
    for symbol in ("type_class", "selection", "%BEP", "NPSHa", "P_abs", "P_motor", "T_shaft"):
        assert by_symbol[symbol].verification is VerificationStatus.EXPERIMENTAL, symbol
        assert any(issue.severity.value == "warning" for issue in by_symbol[symbol].issues), symbol


def test_npsh_failure_flags_cavitation(ctx):
    tree = _tree(ctx, npsh_available_m=2.0)
    npsh = _by_symbol(tree)["NPSHa"]
    assert npsh.verdict.value == "fail"
    assert any("cavitation" in issue.message for issue in npsh.issues)


def test_bearing_life_matches_iso_281(ctx):
    tree = _tree(ctx)
    life = _by_symbol(tree)["L10h"]
    expected = (1.0e6 / (60.0 * 3600.0)) * (80000.0 / 4000.0) ** 3
    assert life.value == pytest.approx(expected, rel=1e-12)
    assert life.citation.standard == "ISO 281"
    assert life.verdict.value == "pass"


def test_bearing_life_fails_below_api_minimum(ctx):
    tree = _tree(ctx, radial_bearing_dynamic_load_n=20000.0)
    life = _by_symbol(tree)["L10h"]
    assert life.verdict.value == "fail"


def test_shaft_combined_stress_and_safety_factor(ctx):
    tree = _tree(ctx)
    by_symbol = _by_symbol(tree)
    torque = by_symbol["T_shaft"].value
    moment = by_symbol["M_shaft"].value
    diameter = 0.03
    section = 3.141592653589793 * diameter**3
    expected_sigma = ((32.0 * moment / section) ** 2 + 3.0 * (16.0 * torque / section) ** 2) ** 0.5
    assert by_symbol["sigma_eq"].value == pytest.approx(expected_sigma, rel=1e-12)
    assert by_symbol["SF_shaft"].value > 1.0
    # Deflection is well below the 0.05 mm API 610 seal-chamber limit.
    assert by_symbol["delta_seal"].value < 0.05e-3
    assert by_symbol["delta_seal"].verdict.value == "pass"


def test_seal_chamber_deflection_fails_with_a_soft_shaft(ctx):
    tree = _tree(ctx, shaft_diameter_mm=8.0, shaft_radial_load_n=2000.0)
    delta = _by_symbol(tree)["delta_seal"]
    assert delta.verdict.value == "fail"


def test_casing_mawp_and_hydrotest(ctx):
    tree = _tree(ctx)
    by_symbol = _by_symbol(tree)
    assert by_symbol["t_casing"].verdict.value == "pass"
    assert by_symbol["P_casing"].verdict.value == "pass"
    assert by_symbol["P_T"].value == pytest.approx(1.5 * by_symbol["P_casing"].value, rel=1e-12)


def test_thin_casing_fails(ctx):
    tree = _tree(ctx, provided_casing_thickness_mm=4.0)
    assert _by_symbol(tree)["t_casing"].verdict.value == "fail"
    assert tree.overall_verdict().value == "fail"


def test_provided_casing_below_corrosion_is_a_validation_error(ctx):
    bad = PumpInputs(**{**_KWARGS, "provided_casing_thickness_mm": 3.0})
    issues = _pack().validate(bad)
    assert any(issue.severity.value == "error" for issue in issues)
    with pytest.raises(ValidationError):
        _pack().calculate(bad, ctx)


def test_provisional_material_downgrades_casing(ctx):
    tree = _tree(ctx)
    by_symbol = _by_symbol(tree)
    assert by_symbol["t_casing"].verification is VerificationStatus.EXPERIMENTAL
    assert by_symbol["P_casing"].verification is VerificationStatus.EXPERIMENTAL
    messages = [issue.message for issue in by_symbol["P_casing"].issues]
    assert any("provisional" in message for message in messages)


def test_nozzle_loads_pass_and_fail_per_nozzle(ctx):
    tree = _tree(ctx, loads=_LOADS)
    by_symbol = _by_symbol(tree)
    assert by_symbol["nozzle_S1"].verdict.value == "pass"
    assert by_symbol["nozzle_D1"].verdict.value == "fail"
    assert by_symbol["nozzle_D1"].verification is VerificationStatus.EXPERIMENTAL
    assert tree.overall_verdict().value == "fail"


def test_seal_selection_is_screening_only(ctx):
    tree = _tree(ctx, seal_hazardous=True)
    seal = _by_symbol(tree)["seal_arrangement"]
    assert seal.verification is VerificationStatus.EXPERIMENTAL
    assert "Arrangement 3" in seal.substitutions["arrangement"]
    assert any("screening" in issue.message for issue in seal.issues)


def test_sour_service_flags_nace(ctx):
    tree = _tree(ctx, h2s_present=True, service="sour hydrocarbon")
    material = _by_symbol(tree)["material_class"]
    assert material.substitutions["NACE"] == "NACE MR0175 / ISO 15156 flagged"
    assert any("NACE" in issue.message for issue in material.issues)


def test_material_class_chloride_screening(ctx):
    tree = _tree(ctx, service="cooling water", chloride_ppm=200.0)
    material = _by_symbol(tree)["material_class"]
    assert "duplex" in material.substitutions["material class (screening)"].lower()


def test_vibration_limit(ctx):
    tree = _tree(ctx, vibration_velocity_mm_s=5.0)
    assert _by_symbol(tree)["v_rms"].verdict.value == "fail"


def test_auto_speed_is_selected(ctx):
    tree = _tree(ctx, rated_speed_rpm=None)
    selection = _by_symbol(tree)["selection"]
    assert selection.substitutions["speed"].endswith("rpm")
    assert _by_symbol(tree)["Ns"].verification.value == "verified"


def test_validate_blocks_bad_shaft_offset_and_phases():
    bad_offset = PumpInputs(**{**_KWARGS, "shaft_load_offset_mm": 500.0})
    assert any(issue.severity.value == "error" for issue in _pack().validate(bad_offset))
    invalid_phases = PumpInputs(**{**_KWARGS, "motor_phases": 2})
    assert any(issue.severity.value == "error" for issue in _pack().validate(invalid_phases))
    with pytest.raises(PydanticValidationError):
        PumpInputs(**{**_KWARGS, "motor_phases": 4})


def test_datasheet_rows_are_assembled(ctx):
    tree = _tree(ctx)
    rows = pump_datasheet_rows(PumpInputs(**_KWARGS), tree)
    labels = [label for label, _value in rows]
    assert "— General —" in labels
    assert "Specific speed Ns" in labels
    assert "Casing MAWP" in labels
    values = dict(rows)
    assert values["Selected model"] == "PU-SAMPLE-OH2"
    assert values["Equipment tag"] == "P-101"


def test_ga_drawing_writes_dxf_and_pdf(ctx, tmp_path):
    import ezdxf

    tree = _tree(ctx)
    drawing = pump_ga_from(PumpInputs(**_KWARGS), tree)
    dxf_path = write_dxf(drawing, tmp_path / "pump.dxf")
    pdf_path = write_pdf(drawing, tmp_path / "pump.pdf")
    assert dxf_path.is_file() and dxf_path.stat().st_size > 1000
    assert pdf_path.is_file() and pdf_path.stat().st_size > 500
    doc = ezdxf.readfile(dxf_path)
    names = {layer.dxf.name for layer in doc.layers}
    assert {"GEOMETRY", "DIMENSIONS", "ANNOTATION", "TITLEBLOCK", "CENTERLINE"} <= names
    texts = [entity.dxf.text for entity in doc.modelspace().query("TEXT")]
    assert any("PUMP GENERAL ARRANGEMENT" in text for text in texts)
    assert any("P-101" in text for text in texts)
