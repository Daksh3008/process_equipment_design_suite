"""Piping pack orchestration (PS-1..PS-3)."""

from __future__ import annotations

from pydantic import BaseModel

from ...calc import pipe as pipe_calc
from ...calc.common import margin_verdict, propagate_experimental_children
from ...core.calc import CalcContext
from ...core.provenance import VerificationStatus
from ...core.result import Issue, Result, ResultTree, Severity
from ...core.units import to_base
from ...core.validation import IssueCollector, ValidationError
from .model import PipeInputs


class PipePack:
    """The piping equipment pack (B31.3)."""

    family = "piping"
    Input = PipeInputs

    def validate(self, inputs: BaseModel) -> list[Issue]:
        if not isinstance(inputs, PipeInputs):
            raise TypeError(f"expected PipeInputs, got {type(inputs).__name__}")
        collector = IssueCollector()
        if inputs.outside_diameter_mm <= 0:
            collector.error("outside diameter must be > 0", field="outside_diameter_mm")
        if inputs.design_pressure_mpa <= 0:
            collector.error("design pressure must be > 0", field="design_pressure_mpa")
        if not 0.0 <= inputs.y_factor <= 1.0:
            collector.error("y factor must lie in [0, 1]", field="y_factor")
        return collector.issues

    def calculate(self, inputs: BaseModel, ctx: CalcContext) -> ResultTree:
        if not isinstance(inputs, PipeInputs):
            raise TypeError(f"expected PipeInputs, got {type(inputs).__name__}")
        issues = self.validate(inputs)
        if any(issue.severity is Severity.ERROR for issue in issues):
            raise ValidationError(issues)

        editions = ctx.editions
        to_m = lambda value: to_base(value, "mm", "length")

        diameter = to_m(inputs.outside_diameter_mm)
        pressure = to_base(inputs.design_pressure_mpa, "MPa", "pressure")
        material = ctx.materials.get(inputs.material_key)
        stress = material.allowable_stress_at(inputs.design_temperature_c)
        corrosion = to_m(inputs.corrosion_allowance_mm)
        provided_wall = (
            to_m(inputs.provided_wall_thickness_mm) if inputs.provided_wall_thickness_mm is not None else None
        )

        tree = ResultTree(name=inputs.tag, governing_case="design")
        thickness = pipe_calc.straight_pipe_thickness(
            pressure, diameter, stress, inputs.weld_joint_factor, inputs.y_factor,
            editions, corrosion, inputs.mill_tolerance_pct,
        )
        tree.add(thickness)

        pressure_thickness = thickness.children[0].value
        net_wall = (provided_wall - corrosion) if provided_wall is not None else pressure_thickness
        mawp = pipe_calc.pipe_mawp(
            net_wall, diameter, stress, inputs.weld_joint_factor, inputs.y_factor, editions
        )
        mawp.verdict, mawp.margin = margin_verdict(_value(mawp), pressure)
        if _is_provisional(material.provenance.checked_by):
            note = Issue(
                severity=Severity.WARNING,
                message=(
                    f"Material data for {material.key} is provisional "
                    f"({material.provenance.checked_by})."
                ),
                rationale="Data policy: unreviewed data must not back a verified result.",
            )
            thickness.verification = VerificationStatus.EXPERIMENTAL
            mawp.verification = VerificationStatus.EXPERIMENTAL
            thickness.issues.append(note)
            mawp.issues.append(note)
        tree.add(mawp)

        if provided_wall is not None:
            thickness.verdict, thickness.margin = margin_verdict(provided_wall, _value(thickness))

        if inputs.branch_outside_diameter_mm is not None:
            run_excess = (
                provided_wall - corrosion - pressure_thickness if provided_wall is not None else 0.0
            )
            tree.add(
                pipe_calc.branch_reinforcement_check(
                    to_m(inputs.branch_outside_diameter_mm),
                    pressure_thickness,
                    run_excess,
                    0.0,
                    editions,
                )
            )
        if _is_provisional(material.provenance.checked_by):
            propagate_experimental_children(tree)
        return tree


def _is_provisional(checked_by: str) -> bool:
    return "UNVERIFIED" in checked_by.upper()


def _value(result: Result) -> float:
    if result.value is None:
        raise ValueError(f"calculation {result.symbol!r} produced no numeric value")
    return result.value