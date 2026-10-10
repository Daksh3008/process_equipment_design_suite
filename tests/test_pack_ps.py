"""Piping pack end-to-end tests (PS-1..PS-3)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError as PydanticValidationError

from pemds.packs.ps import PipePack
from pemds.packs.ps.model import PipeInputs

_KWARGS = {
    "tag": "L-101",
    "outside_diameter_mm": 168.3,
    "design_pressure_mpa": 1.5,
    "design_temperature_c": 150.0,
    "material_key": "SA-106-B",
    "corrosion_allowance_mm": 1.0,
    "weld_joint_factor": 1.0,
    "y_factor": 0.4,
    "mill_tolerance_pct": 12.5,
    "provided_wall_thickness_mm": 7.11,
}


def _pack():
    return PipePack()


def test_pipe_end_to_end(ctx):
    tree = _pack().calculate(PipeInputs(**_KWARGS), ctx)
    by_symbol = {r.symbol: r for r in tree.roots}
    assert by_symbol["t"].value < 0.00711  # 7.11 mm provided wall is ample
    assert by_symbol["P"].verdict.value == "pass"
    assert tree.overall_verdict().value == "pass"


def test_pipe_undersized_wall_fails(ctx):
    thin = dict(_KWARGS, provided_wall_thickness_mm=2.0)
    tree = _pack().calculate(PipeInputs(**thin), ctx)
    mawp = next(r for r in tree.roots if r.symbol == "P")
    assert mawp.verdict.value == "fail"
    assert tree.overall_verdict().value == "fail"


def test_pipe_validation_blocks_bad_y_factor():
    # Field-level guards reject out-of-range values before the pack sees them.
    with pytest.raises(PydanticValidationError):
        PipeInputs(**dict(_KWARGS, y_factor=2.0))


def test_branch_check_included_when_specified(ctx):
    with_branch = dict(_KWARGS, branch_outside_diameter_mm=60.3)
    tree = _pack().calculate(PipeInputs(**with_branch), ctx)
    assert any(r.symbol == "A_avail" for r in tree.roots)