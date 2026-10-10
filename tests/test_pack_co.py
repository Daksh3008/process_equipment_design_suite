"""Column / reactor pack end-to-end tests (CO-1..CO-3, VAL-2)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from pemds.core.validation import ValidationError
from pemds.packs.co import ColumnPack
from pemds.packs.co.model import ColumnInputs

_BASE = dict(  # noqa: C408 - keyword form reads better for a fixture
    tag="C-101",
    inside_diameter_mm=2000.0,
    tangent_to_tangent_mm=20000.0,
    skirt_height_mm=1500.0,
    material_key="SA-516-70",
    design_pressure_mpa=1.0,
    design_temperature_c=150.0,
    joint_type="1",
    radiography="full",
    corrosion_allowance_mm=3.0,
    mill_undertolerance_mm=0.3,
    provided_shell_thickness_mm=14.0,
    operating_weight_kg=150000.0,
    bolt_circle_diameter_mm=2200.0,
    num_anchor_bolts=12,
    provided_bolt_area_mm2=2000.0,
    allowable_bolt_tensile_mpa=138.0,
    base_plate_projection_mm=60.0,
    foundation_bearing_pressure_kpa=3000.0,
    allowable_base_plate_bending_mpa=165.0,
    wind_speed_m_s=45.0,
    exposure_factor_kz=1.2,
    topographic_factor_kzt=1.0,
    directionality_factor_kd=0.85,
    seismic_cs=0.1,
)


def _pack():
    return ColumnPack()


def test_column_pressure_and_governing_moment(ctx):
    tree = _pack().calculate(ColumnInputs(**_BASE), ctx)
    by_symbol = {r.symbol: r for r in tree.roots}
    assert by_symbol["t_shell"].value == pytest.approx(0.010578020378, rel=1e-9)
    assert by_symbol["t_shell"].verdict.value == "pass"
    governing = by_symbol["M_governing"]
    children = {child.symbol: child.value for child in governing.children}
    assert set(children) == {"M_wind", "M_seismic"}
    assert governing.value == pytest.approx(max(children.values()), rel=1e-12)
    assert governing.substitutions["governing"] == "seismic"


def test_column_combined_stress_and_anchor_pass(ctx):
    tree = _pack().calculate(ColumnInputs(**_BASE), ctx)
    by_symbol = {r.symbol: r for r in tree.roots}
    assert by_symbol["sigma_total"].verdict.value == "pass"
    assert by_symbol["sigma_total"].citation.standard == "ASME BPVC Section VIII, Division 1"
    assert by_symbol["A_bolt_req"].verdict.value == "pass"
    assert by_symbol["t_bp"].value > 0
    assert by_symbol["t_bp"].citation.standard == "ACI 318"


def test_column_wind_pressure_formula(ctx):
    tree = _pack().calculate(ColumnInputs(**_BASE), ctx)
    governing = next(r for r in tree.roots if r.symbol == "M_governing")
    wind = next(child for child in governing.children if child.symbol == "M_wind")
    qz = next(child for child in wind.children if child.symbol == "qz")
    expected_qz = 0.613 * 1.2 * 1.0 * 0.85 * 45.0**2
    assert qz.value == pytest.approx(expected_qz, rel=1e-12)
    assert qz.kind == "pressure"


def test_column_results_are_experimental_everywhere(ctx):
    tree = _pack().calculate(ColumnInputs(**_BASE), ctx)
    assert tree.flatten()
    for result in tree.flatten():
        assert result.verification.value == "experimental", result.symbol
    messages = [issue.message for result in tree.flatten() for issue in result.issues]
    assert any("EXPERIMENTAL" in message for message in messages)


def test_column_undersized_anchor_bolts_fail(ctx):
    tree = _pack().calculate(ColumnInputs(**dict(_BASE, provided_bolt_area_mm2=353.0)), ctx)
    bolt = next(r for r in tree.roots if r.symbol == "A_bolt_req")
    assert bolt.verdict.value == "fail"
    assert bolt.margin is not None and bolt.margin < 0


def test_column_validation_blocks_single_bolt():
    # The field guard rejects a single bolt before the pack sees it.
    with pytest.raises(PydanticValidationError):
        ColumnInputs(**dict(_BASE, num_anchor_bolts=1))


def test_column_validation_blocks_thin_provided_shell(ctx):
    bad = ColumnInputs(**dict(_BASE, provided_shell_thickness_mm=2.0))  # CA 3.0 + mill 0.3
    assert any(i.severity.value == "error" for i in _pack().validate(bad))
    with pytest.raises(ValidationError):
        _pack().calculate(bad, ctx)


def test_column_determinism(ctx):
    import json

    inputs = ColumnInputs(**_BASE)
    first = json.dumps(_pack().calculate(inputs, ctx).to_dict(), sort_keys=True)
    second = json.dumps(_pack().calculate(inputs, ctx).to_dict(), sort_keys=True)
    assert first == second
