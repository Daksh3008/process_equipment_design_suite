"""Heat-exchanger pack end-to-end tests (HX-1..HX-3, VAL-2)."""

from __future__ import annotations

import pytest

from pemds.core.validation import ValidationError
from pemds.packs.hx import HeatExchangerPack
from pemds.packs.hx.model import HeatExchangerInputs

_BASE = dict(  # noqa: C408 - keyword form reads better for a fixture
    tag="E-101",
    shell_inside_diameter_mm=800.0,
    shell_tangent_to_tangent_mm=3000.0,
    material_key="SA-516-70",
    design_pressure_mpa=1.0,
    design_temperature_c=150.0,
    joint_type="1",
    radiography="full",
    corrosion_allowance_mm=3.0,
    mill_undertolerance_mm=0.3,
    provided_shell_thickness_mm=12.0,
    channel_cover_type="flat",
    channel_flat_factor_c=0.33,
    provided_channel_thickness_mm=20.0,
    effective_gasket_diameter_mm=800.0,
    tubesheet_factor_f=1.0,
    provided_tubesheet_thickness_mm=80.0,
    tube_outside_diameter_mm=19.05,
    tube_wall_thickness_mm=2.11,
    tube_pitch_mm=23.8125,
    tube_count=200,
    tube_joint_type="rolled",
    tube_joint_shear_strength_mpa=70.0,
    tube_joint_length_mm=40.0,
    tube_weld_leg_mm=3.0,
)


def _pack():
    return HeatExchangerPack()


def test_exchanger_shell_channel_and_tubesheet(ctx):
    tree = _pack().calculate(HeatExchangerInputs(**_BASE), ctx)
    by_symbol = {r.symbol: r for r in tree.roots}
    # shell: 1e6*0.4/(2*(138e6 ...)) style; circ dominates
    assert by_symbol["t_shell"].value == pytest.approx(0.00621120815, rel=1e-6)
    # flat channel cover: 0.8*sqrt(0.33/138) + 0.003 CA + 0.0003 mill
    assert by_symbol["t_channel"].value == pytest.approx(0.0424210, rel=1e-5)
    # tubesheet: 1.0*0.8*sqrt(1/138) + 0.003 CA + 0.0003 mill
    assert by_symbol["t_tubesheet"].value == pytest.approx(0.0711005703, rel=1e-6)
    assert by_symbol["t_shell"].verdict.value == "pass"
    assert by_symbol["t_tubesheet"].verdict.value == "pass"


def test_exchanger_welded_joint_uses_weld_capacity(ctx):
    welded = _pack().calculate(
        HeatExchangerInputs(**dict(_BASE, tube_joint_type="welded")), ctx
    )
    joint = next(r for r in welded.roots if r.symbol == "F_joint")
    assert joint.verdict.value == "pass"
    rolled = _pack().calculate(HeatExchangerInputs(**_BASE), ctx)
    rolled_joint = next(r for r in rolled.roots if r.symbol == "F_joint")
    # Welded joints are sized by the weld leg; the numeric capacities must differ.
    assert joint.value != rolled_joint.value or joint.formula != rolled_joint.formula


def test_exchanger_tube_layout_and_joint(ctx):
    tree = _pack().calculate(HeatExchangerInputs(**_BASE), ctx)
    tubesheet = next(r for r in tree.roots if r.symbol == "t_tubesheet")
    layout = next(child for child in tubesheet.children if child.symbol == "e_ligament")
    assert layout.value == pytest.approx(0.2, rel=1e-9)
    assert layout.citation.standard == "TEMA Standards"
    joint = next(r for r in tree.roots if r.symbol == "F_joint")
    assert joint.verdict.value == "pass"


def test_exchanger_results_are_experimental_everywhere(ctx):
    tree = _pack().calculate(HeatExchangerInputs(**_BASE), ctx)
    assert tree.flatten()
    for result in tree.flatten():
        assert result.verification.value == "experimental", result.symbol
    messages = [issue.message for result in tree.flatten() for issue in result.issues]
    assert any("EXPERIMENTAL" in message for message in messages)
    assert any("UHX" in message for message in messages)


def test_exchanger_undersized_tubesheet_fails(ctx):
    tree = _pack().calculate(
        HeatExchangerInputs(**dict(_BASE, provided_tubesheet_thickness_mm=50.0)), ctx
    )
    tubesheet = next(r for r in tree.roots if r.symbol == "t_tubesheet")
    assert tubesheet.verdict.value == "fail"


def test_exchanger_undersized_shell_fails(ctx):
    tree = _pack().calculate(
        HeatExchangerInputs(**dict(_BASE, provided_shell_thickness_mm=6.0)), ctx
    )
    shell = next(r for r in tree.roots if r.symbol == "t_shell")
    assert shell.verdict.value == "fail"


def test_exchanger_weak_weld_joint_fails(ctx):
    weak = dict(
        _BASE,
        design_pressure_mpa=10.0,
        tube_joint_type="welded",
        tube_weld_leg_mm=1.0,
        tube_joint_shear_strength_mpa=20.0,
    )
    tree = _pack().calculate(HeatExchangerInputs(**weak), ctx)
    joint = next(r for r in tree.roots if r.symbol == "F_joint")
    assert joint.verdict.value == "fail"
    assert joint.margin is not None and joint.margin < 0


def test_exchanger_expansion_joint_note(ctx):
    tree = _pack().calculate(HeatExchangerInputs(**dict(_BASE, include_expansion_joint=True)), ctx)
    joint = next(r for r in tree.roots if r.symbol == "F_joint")
    assert any("expansion joint" in issue.message.lower() for issue in joint.issues)


def test_exchanger_validation_blocks_bad_pitch(ctx):
    bad = HeatExchangerInputs(**dict(_BASE, tube_pitch_mm=19.0))
    assert any(i.severity.value == "error" for i in _pack().validate(bad))
    with pytest.raises(ValidationError):
        _pack().calculate(bad, ctx)
