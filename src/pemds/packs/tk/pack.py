"""Storage-tank pack orchestration (FR-TK, TK-1..TK-3) — EXPERIMENTAL (VAL-2).

Builds the governing shell-course thickness, a preliminary roof sizing and an
optional shell-opening reinforcement check. The pack converts user units to
internal SI at this boundary and performs no I/O.

Every result in the tree is EXPERIMENTAL: each calculation is decorated with the
experimental status, and the governing shell result and the top-level ``status``
summary carry a warning that names the experimental status.
"""

from __future__ import annotations

import math

from pydantic import BaseModel

from ...calc import tank as tank_calc
from ...calc.common import make_result, margin_verdict
from ...core.calc import CalcContext, citation_of
from ...core.provenance import VerificationStatus
from ...core.result import Issue, Result, ResultTree, Severity, Verdict
from ...core.standards import API_650
from ...core.units import format_value, to_base
from ...core.validation import IssueCollector
from .model import StorageTankInputs

_EXPERIMENTAL_MESSAGE = (
    "The storage-tank (TK) pack is EXPERIMENTAL in v1.5 (VAL-2); results must not "
    "be used for construction without independent verification."
)


class StorageTankPack:
    """The storage-tank equipment pack (API 650)."""

    family = "storage_tank"
    Input = StorageTankInputs

    def validate(self, inputs: BaseModel) -> list[Issue]:
        if not isinstance(inputs, StorageTankInputs):
            raise TypeError(f"expected StorageTankInputs, got {type(inputs).__name__}")
        collector = IssueCollector()
        if inputs.diameter_mm <= 0:
            collector.error("tank diameter must be > 0", field="diameter_mm")
        if inputs.design_liquid_height_mm <= 0:
            collector.error("design liquid height must be > 0", field="design_liquid_height_mm")
        if not 0.0 < inputs.joint_efficiency <= 1.0:
            collector.error("joint efficiency must lie in (0, 1]", field="joint_efficiency")
        if not math.isfinite(inputs.design_temperature_c):
            collector.error("design temperature must be finite", field="design_temperature_c")
        if (
            inputs.provided_shell_thickness_mm is not None
            and inputs.provided_shell_thickness_mm <= inputs.corrosion_allowance_mm
        ):
            collector.error(
                "provided shell thickness must exceed the corrosion allowance",
                field="provided_shell_thickness_mm",
            )
        if inputs.roof_type == "dome" and not 0.0 < inputs.roof_rise_mm < inputs.diameter_mm / 2.0:
            collector.error(
                "dome rise must lie between 0 and half the tank diameter",
                field="roof_rise_mm",
            )
        if inputs.opening_neck_thickness_mm is not None and inputs.opening_outside_diameter_mm is None:
            collector.error(
                "an opening neck thickness requires an opening outside diameter",
                field="opening_outside_diameter_mm",
            )
        if (
            inputs.opening_outside_diameter_mm is not None
            and inputs.opening_neck_thickness_mm is not None
            and 2.0 * inputs.opening_neck_thickness_mm >= inputs.opening_outside_diameter_mm
        ):
            collector.error(
                "opening neck thickness must be below half the outside diameter so a bore remains",
                field="opening_neck_thickness_mm",
            )
        return collector.issues

    def calculate(self, inputs: BaseModel, ctx: CalcContext) -> ResultTree:
        if not isinstance(inputs, StorageTankInputs):
            raise TypeError(f"expected StorageTankInputs, got {type(inputs).__name__}")
        collector = IssueCollector()
        for issue in self.validate(inputs):
            if issue.severity is Severity.ERROR:
                collector.error(issue.message, issue.field)
        collector.raise_if_errors()

        editions = ctx.editions
        to_m = lambda value: to_base(value, "mm", "length")

        diameter = to_m(inputs.diameter_mm)
        liquid_height = to_m(inputs.design_liquid_height_mm)
        corrosion = to_m(inputs.corrosion_allowance_mm)
        material = ctx.materials.get(inputs.material_key)
        stress = material.allowable_stress_at(inputs.design_temperature_c)

        tree = ResultTree(name=inputs.tag, governing_case="design (hydrostatic)")

        # --- TK-1 shell courses (bottom thickest, top thinner) -----------------
        plate_width = to_m(inputs.plate_width_mm)
        plate_length = to_m(inputs.plate_length_mm)
        provided = (
            to_m(inputs.provided_shell_thickness_mm)
            if inputs.provided_shell_thickness_mm is not None
            else None
        )
        shell = tank_calc.shell_courses(
            diameter,
            liquid_height,
            plate_width,
            inputs.specific_gravity,
            stress,
            inputs.joint_efficiency,
            editions,
            corrosion,
            provided,
        )
        shell.issues.append(_experimental_issue(shell.citation))
        _add_material_note(shell, material, "material_key")
        required_pressure = _value(shell) - corrosion
        shell_metal = required_pressure
        if provided is not None:
            shell_metal = provided - corrosion
            shell.verdict, shell.margin = margin_verdict(provided, _value(shell))
            shell.substitutions["provided"] = format_value(provided, "m")
        tree.add(shell)

        # --- TK-1 plate take-off and zig-zag course arrangement ---------------
        plates = tank_calc.plate_quantities(
            diameter, liquid_height, plate_width, plate_length, editions
        )
        plates.issues.append(_experimental_issue(plates.citation))
        tree.add(plates)

        # --- top-level experimental status (VAL-2) ----------------------------
        tree.add(self._status(editions))

        # --- TK-2 roof sizing (optional) --------------------------------------
        if inputs.include_roof_calculation:
            roof = tank_calc.roof_sizing(
                inputs.roof_type,
                diameter,
                inputs.roof_slope_ratio,
                to_m(inputs.roof_rise_mm),
                to_base(inputs.roof_live_load_kpa, "kPa", "pressure"),
                to_base(inputs.roof_dead_load_kpa, "kPa", "pressure"),
                stress,
                editions,
                corrosion,
            )
            roof.issues.append(_experimental_issue(roof.citation))
            tree.add(roof)

        # --- TK-3 opening reinforcement ---------------------------------------
        if inputs.opening_outside_diameter_mm is not None:
            outside = to_m(inputs.opening_outside_diameter_mm)
            neck = (
                to_m(inputs.opening_neck_thickness_mm)
                if inputs.opening_neck_thickness_mm is not None
                else None
            )
            opening = outside - 2.0 * neck if neck is not None else outside
            if opening <= 0:  # pragma: no cover - validation blocks this before calculate
                raise ValueError("opening neck thickness leaves no bore")
            shell_excess = max(0.0, shell_metal - required_pressure)
            nozzle_excess = max(0.0, neck - required_pressure) if neck is not None else 0.0
            opening_result = tank_calc.opening_reinforcement_check(
                opening,
                required_pressure,
                shell_excess,
                nozzle_excess,
                to_m(inputs.opening_projection_mm),
                editions,
            )
            opening_result.issues.append(_experimental_issue(opening_result.citation))
            tree.add(opening_result)

        return tree

    @staticmethod
    def _status(editions) -> Result:
        citation = citation_of(API_650, "5.6 shell design", editions, "S5")
        return make_result(
            symbol="status",
            value=None,
            kind="dimensionless",
            formula="experimental (VAL-2): independent verification required before use",
            substitutions={"verification": VerificationStatus.EXPERIMENTAL.value},
            citation=citation,
            inputs_used=[],
            verdict=Verdict.NA,
            verification=VerificationStatus.EXPERIMENTAL,
            issues=[_experimental_issue(citation)],
        )


def _experimental_issue(citation) -> Issue:
    return Issue(
        severity=Severity.WARNING,
        message=_EXPERIMENTAL_MESSAGE,
        rationale=(
            "TK-1..TK-3 are transparent API 650 subsets and are not validated against "
            "worked examples in v1.5 (VAL-2)."
        ),
        citation=citation,
    )


def _add_material_note(result: Result, material, field: str) -> None:
    if "UNVERIFIED" in material.provenance.checked_by.upper():
        result.issues.append(
            Issue(
                severity=Severity.WARNING,
                message=(
                    f"Material data for {material.key} is provisional "
                    f"({material.provenance.checked_by})."
                ),
                field=field,
                rationale="Data policy: unreviewed material data must not back a verified result.",
            )
        )


def _value(result: Result) -> float:
    if result.value is None:
        raise ValueError(f"calculation {result.symbol!r} produced no numeric value")
    return result.value
