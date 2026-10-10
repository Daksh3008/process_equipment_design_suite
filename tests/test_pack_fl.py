"""Flange pack end-to-end tests (FR-FL, FL-1..FL-3)."""

from __future__ import annotations

import json
import math

import pytest
from pydantic import ValidationError as PydanticValidationError

from pemds.calc import flange as flange_calc
from pemds.packs.fl import FlangeInputs, FlangePack
from pemds.packs.fl.model import ConnectionInput

_KWARGS = dict(  # noqa: C408 - keyword form reads better for a fixture
    tag="FL-101",
    size="2",
    material_group="1.1",
    design_pressure_mpa=1.0,
    design_temperature_c=100.0,
    gasket_type="spiral-wound",
    facing="raised_face",
    gasket_mean_diameter_mm=100.0,
    gasket_contact_width_mm=4.5,
    bolt_allowable_stress_mpa=138.0,
    nut_factor_k=0.2,
    connections=[ConnectionInput(tag="N1", size="2")],
)


def _pack() -> FlangePack:
    return FlangePack()


def test_flange_pack_end_to_end(ctx):
    tree = _pack().calculate(FlangeInputs(**_KWARGS), ctx)
    roots = {r.symbol: r for r in tree.roots}
    assert {"flange_rating", "bolt_up", "connection_N1"} <= set(roots)
    # Class 150 group 1.1 rating at 100 degC is 1.79 MPa in the demonstration set.
    assert roots["flange_rating"].value == pytest.approx(1.79e6, rel=1e-12)
    assert roots["flange_rating"].verdict.value == "pass"
    assert roots["bolt_up"].verdict.value == "pass"
    assert tree.overall_verdict().value == "pass"


def test_fl1_failure_propagates_to_the_pack(ctx):
    over = FlangeInputs(**dict(_KWARGS, design_pressure_mpa=20.0))
    tree = _pack().calculate(over, ctx)
    rating = next(r for r in tree.roots if r.symbol == "flange_rating")
    assert rating.verdict.value == "fail"
    assert tree.overall_verdict().value == "fail"
    messages = [issue.message for result in tree.flatten() for issue in result.issues]
    assert any("nearest upgrade" in message for message in messages)


def test_rating_lookup_is_exact_at_a_tabulated_temperature(ctx):
    result = flange_calc.pressure_temp_rating("2", "1.1", 150, 100.0, ctx.editions)
    assert result.value == pytest.approx(1.79e6, rel=1e-12)
    assert result.unit == "pascal"
    assert result.citation.standard == "ASME B16.5"
    assert result.verification.value == "experimental"
    assert any(issue.severity.value == "warning" for issue in result.issues)


def test_rating_step_lookup_is_conservative_between_steps(ctx):
    result = flange_calc.pressure_temp_rating("2", "1.1", 150, 50.0, ctx.editions)
    assert result.value == pytest.approx(1.79e6, rel=1e-12)  # next higher step is 100 degC


def test_select_class_picks_the_lowest_qualifying_class(ctx):
    low = flange_calc.select_class("2", "1.1", 1.0e6, 100.0, ctx.editions)
    assert int(low.value) == 150
    assert low.verdict.value == "pass"
    middle = flange_calc.select_class("2", "1.1", 2.0e6, 100.0, ctx.editions)
    assert int(middle.value) == 300
    high = flange_calc.select_class("2", "1.1", 7.0e6, 100.0, ctx.editions)
    assert int(high.value) == 600


def test_select_class_reports_failure_with_nearest_upgrade(ctx):
    result = flange_calc.select_class("2", "1.1", 20.0e6, 100.0, ctx.editions)
    assert result.verdict.value == "fail"
    assert int(result.value) == 600
    assert result.margin is not None and result.margin < 0
    messages = [issue.message for issue in result.issues]
    assert any("Class 600" in message and "upgrade" in message for message in messages)


def test_minimum_class_raises_the_floor(ctx):
    result = flange_calc.select_class("2", "1.1", 1.0e6, 100.0, ctx.editions, minimum_class=600)
    assert int(result.value) == 600


def test_bolt_up_check_hand_calculation(ctx):
    result = flange_calc.bolt_up_check(
        2.0e6, 0.1, 0.00225, 3.0, 69.0e6, 4, 145.8e-6, 0.015875, 138.0e6, 0.2, ctx.editions
    )
    hydrostatic = math.pi / 4.0 * 0.1**2 * 2.0e6
    gasket_operating = 2.0 * 0.00225 * math.pi * 0.1 * 3.0 * 2.0e6
    operating = hydrostatic + gasket_operating
    seating = math.pi * 0.00225 * 0.1 * 69.0e6
    required = max(operating, seating) / 138.0e6
    available = 4 * 145.8e-6
    assert result.value == pytest.approx(available, rel=1e-12)
    assert result.verdict.value == "pass"
    assert result.margin == pytest.approx((available - required) / required, rel=1e-12)
    torque = next(child for child in result.children if child.symbol == "T_bolt")
    assert torque.value == pytest.approx(0.2 * 0.015875 * (max(operating, seating) / 4), rel=1e-12)
    assert torque.unit == "N*m"
    assert result.verification.value == "experimental"
    assert any("simplified" in issue.message for issue in result.issues)


def test_bolt_area_fails_at_high_pressure(ctx):
    result = flange_calc.bolt_up_check(
        20.0e6, 0.1, 0.00225, 3.0, 69.0e6, 4, 145.8e-6, 0.015875, 138.0e6, 0.2, ctx.editions
    )
    assert result.verdict.value == "fail"
    assert result.margin is not None and result.margin < 0


def test_mating_flange_pair(ctx):
    result = flange_calc.mating_flange_pair(
        "2", 150, "raised_face", "spiral-wound", 4, 15.875, ctx.editions
    )
    assert result.symbol == "flange_pair"
    assert result.value == pytest.approx(2.0)
    assert {child.symbol for child in result.children} == {"flange_upstream", "flange_downstream"}
    assert result.verification.value == "experimental"
    assert result.citation.clause


def test_connection_schedule_selects_per_size_and_floor(ctx):
    inputs = FlangeInputs(
        **dict(
            _KWARGS,
            connections=[
                ConnectionInput(tag="N1", size="2"),
                ConnectionInput(tag="N2", size="4"),
                ConnectionInput(tag="N3", size="2", minimum_class=300),
            ],
        )
    )
    tree = _pack().calculate(inputs, ctx)
    by_symbol = {r.symbol: r for r in tree.roots}
    assert int(by_symbol["connection_N1"].value) == 150
    assert int(by_symbol["connection_N2"].value) == 150
    assert int(by_symbol["connection_N3"].value) == 300
    pair = next(
        child for child in by_symbol["connection_N1"].children if child.symbol == "flange_pair"
    )
    assert pair.substitutions["size (NPS)"] == "2"


def test_validation_blocks_unknown_size(ctx):
    pack = _pack()
    bad = FlangeInputs(**dict(_KWARGS, size="99"))
    assert any(issue.severity.value == "error" for issue in pack.validate(bad))
    from pemds.core.validation import ValidationError

    with pytest.raises(ValidationError):
        pack.calculate(bad, ctx)


def test_unknown_gasket_is_rejected_at_the_model_boundary(ctx):
    # v1.5: gasket type is a closed enum, so the invalid value cannot even be built.
    from pydantic import ValidationError as PydanticValidationError

    with pytest.raises(PydanticValidationError):
        FlangeInputs(**dict(_KWARGS, gasket_type="unobtainium"))


def test_unknown_facing_is_rejected_at_the_model_boundary(ctx):
    from pydantic import ValidationError as PydanticValidationError

    with pytest.raises(PydanticValidationError):
        FlangeInputs(**dict(_KWARGS, facing="banana"))


def test_temperature_outside_the_table_is_a_validation_error(ctx):
    bad = FlangeInputs(**dict(_KWARGS, design_temperature_c=900.0))
    messages = [issue.message for issue in _pack().validate(bad)]
    assert any("tabulated rating range" in message for message in messages)


def test_duplicate_connection_tag_is_a_validation_error(ctx):
    bad = FlangeInputs(
        **dict(
            _KWARGS,
            connections=[ConnectionInput(tag="N1", size="2"), ConnectionInput(tag="N1", size="4")],
        )
    )
    assert any("duplicate" in issue.message for issue in _pack().validate(bad))


def test_nut_factor_field_guard():
    with pytest.raises(PydanticValidationError):
        FlangeInputs(**dict(_KWARGS, nut_factor_k=2.0))


def test_unverified_data_is_surfaced_and_downgrades_verification(ctx):
    tree = _pack().calculate(FlangeInputs(**_KWARGS), ctx)
    messages = [issue.message for result in tree.flatten() for issue in result.issues]
    assert any("provisional" in message for message in messages)
    for result in tree.roots:
        assert result.verification.value == "experimental"


def test_all_nodes_carry_citations(ctx):
    tree = _pack().calculate(FlangeInputs(**_KWARGS), ctx)
    for result in tree.flatten():
        assert result.citation.standard, result.symbol
        assert result.citation.edition, result.symbol
        assert result.citation.clause, result.symbol


def test_determinism(ctx):
    inputs = FlangeInputs(**_KWARGS)
    first = json.dumps(_pack().calculate(inputs, ctx).to_dict(), sort_keys=True)
    second = json.dumps(_pack().calculate(inputs, ctx).to_dict(), sort_keys=True)
    assert first == second
