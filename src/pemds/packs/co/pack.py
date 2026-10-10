"""Column / reactor pack orchestration (FR-CO, CO-1..CO-3) — EXPERIMENTAL (VAL-2).

* CO-1 checks the VIII-1 pressure thickness and the combined pressure + bending
  longitudinal stress at the skirt transition.
* CO-2 checks the anchor-bolt tension/required area and the base-plate thickness.
* CO-3 builds the wind and seismic base moments from ASCE 7 inputs and selects
  the governing one.

Every result in the tree is EXPERIMENTAL and the governing combined-stress result
carries a warning naming the experimental status (VAL-2).
"""

from __future__ import annotations

import math

from pydantic import BaseModel

from ...calc import column as column_calc
from ...calc import joints, minimums
from ...calc import shell as shell_calc
from ...calc.common import make_result, margin_verdict
from ...core.calc import CalcContext, citation_of
from ...core.provenance import VerificationStatus
from ...core.result import Issue, Result, ResultTree, Severity, Verdict
from ...core.standards import ASCE_7
from ...core.units import format_value, to_base
from ...core.validation import IssueCollector
from .model import ColumnInputs

#: Standard gravity, m/s^2.
_G = 9.80665

_EXPERIMENTAL_MESSAGE = (
    "The column/reactor (CO) pack is EXPERIMENTAL in v1.5 (VAL-2); results must not "
    "be used for construction without independent verification."
)


class ColumnPack:
    """The column / reactor equipment pack (VIII-1 + ASCE 7 + ACI 318)."""

    family = "column"
    Input = ColumnInputs

    def validate(self, inputs: BaseModel) -> list[Issue]:
        if not isinstance(inputs, ColumnInputs):
            raise TypeError(f"expected ColumnInputs, got {type(inputs).__name__}")
        collector = IssueCollector()
        if not math.isfinite(inputs.design_temperature_c):
            collector.error("design temperature must be finite", field="design_temperature_c")
        if inputs.num_anchor_bolts < 2:
            collector.error("at least two anchor bolts are required", field="num_anchor_bolts")
        if not math.isfinite(inputs.seismic_cs) or inputs.seismic_cs < 0:
            collector.error("seismic response coefficient must be finite and >= 0", field="seismic_cs")
        addition = inputs.corrosion_allowance_mm + inputs.mill_undertolerance_mm
        if (
            inputs.provided_shell_thickness_mm is not None
            and inputs.provided_shell_thickness_mm <= addition
        ):
            collector.error(
                "provided shell thickness must exceed corrosion allowance + mill undertolerance "
                f"({addition:g} mm)",
                field="provided_shell_thickness_mm",
            )
        return collector.issues

    def calculate(self, inputs: BaseModel, ctx: CalcContext) -> ResultTree:
        if not isinstance(inputs, ColumnInputs):
            raise TypeError(f"expected ColumnInputs, got {type(inputs).__name__}")
        collector = IssueCollector()
        for issue in self.validate(inputs):
            if issue.severity is Severity.ERROR:
                collector.error(issue.message, issue.field)
        collector.raise_if_errors()

        editions = ctx.editions
        to_m = lambda value: to_base(value, "mm", "length")

        diameter = to_m(inputs.inside_diameter_mm)
        radius = diameter / 2.0
        pressure = to_base(inputs.design_pressure_mpa, "MPa", "pressure")
        corrosion = to_m(inputs.corrosion_allowance_mm)
        mill = to_m(inputs.mill_undertolerance_mm)
        material = ctx.materials.get(inputs.material_key)
        stress = material.allowable_stress_at(inputs.design_temperature_c)
        efficiency = _value(joints.joint_efficiency(inputs.joint_type, inputs.radiography, editions))
        minimum_metal = _value(minimums.minimum_shell_thickness(editions))

        tree = ResultTree(name=inputs.tag, governing_case="design + wind/seismic")

        # --- CO-1 pressure thickness (reuse VIII-1) ---------------------------
        circumferential = shell_calc.circumferential_thickness(
            pressure, radius, stress, efficiency, editions, corrosion
        )
        longitudinal = shell_calc.longitudinal_thickness(
            pressure, radius, stress, efficiency, editions, corrosion
        )
        circ_pressure = _value(circumferential) - corrosion
        long_pressure = _value(longitudinal) - corrosion
        required_metal = max(circ_pressure, long_pressure, minimum_metal)
        nominal_shell = required_metal + corrosion + mill
        shell = make_result(
            symbol="t_shell",
            value=nominal_shell,
            kind="length",
            formula="t_shell = max(UG-27(c)(1), UG-27(c)(2), UG-16 min) + CA + mill",
            substitutions={
                "pressure thickness": format_value(max(circ_pressure, long_pressure), "m"),
                "UG-16 minimum": format_value(minimum_metal, "m"),
                "corrosion allowance": format_value(corrosion, "m"),
                "mill undertolerance": format_value(mill, "m"),
                "allowable stress S": format_value(stress, "Pa"),
                "joint efficiency E": f"{efficiency:g}",
            },
            citation=circumferential.citation,
            inputs_used=[
                "inside_diameter_mm",
                "design_pressure_mpa",
                "material_key",
                "joint_type",
                "radiography",
                "corrosion_allowance_mm",
                "mill_undertolerance_mm",
                "provided_shell_thickness_mm",
            ],
            children=[circumferential, longitudinal],
            verification=VerificationStatus.EXPERIMENTAL,
            issues=[_experimental_issue(circumferential.citation)],
        )
        metal = required_metal
        if inputs.provided_shell_thickness_mm is not None:
            provided = to_m(inputs.provided_shell_thickness_mm)
            metal = provided - mill - corrosion
            shell.verdict, shell.margin = margin_verdict(provided, nominal_shell)
            shell.substitutions["provided"] = format_value(provided, "m")
        if metal <= 0:  # pragma: no cover - validation blocks this before calculate
            raise ValueError("provided shell thickness leaves no metal after allowances")
        tree.add(shell)

        # --- CO-3 wind and seismic base moments -------------------------------
        exposed_height = to_m(inputs.tangent_to_tangent_mm) + to_m(inputs.skirt_height_mm)
        outside_diameter = diameter + 2.0 * metal
        wind = column_calc.wind_base_moment(
            outside_diameter,
            exposed_height,
            inputs.wind_speed_m_s,
            inputs.exposure_factor_kz,
            inputs.topographic_factor_kzt,
            inputs.directionality_factor_kd,
            editions,
        )
        weight_n = inputs.operating_weight_kg * _G
        seismic = column_calc.seismic_base_moment(
            inputs.seismic_cs, weight_n, exposed_height, editions
        )
        wind_moment = _value(wind)
        seismic_moment = _value(seismic)
        governing_is_wind = wind_moment >= seismic_moment
        governing = make_result(
            symbol="M_governing",
            value=max(wind_moment, seismic_moment),
            kind="moment",
            formula="M_governing = max(M_wind, M_seismic)",
            substitutions={
                "M_wind": format_value(wind_moment, "N*m"),
                "M_seismic": format_value(seismic_moment, "N*m"),
                "governing": "wind" if governing_is_wind else "seismic",
            },
            citation=citation_of(ASCE_7, "27.3 wind loads", editions, "S8"),
            inputs_used=["wind_speed_m_s", "seismic_cs", "overall_height_mm"],
            children=[wind, seismic],
            verification=VerificationStatus.EXPERIMENTAL,
            issues=[_experimental_issue(citation_of(ASCE_7, "27.3 wind loads", editions, "S8"))],
        )
        tree.add(governing)

        # --- CO-1 skirt-transition combined stress ----------------------------
        combined = column_calc.combined_longitudinal_stress(
            pressure, radius, metal, _value(governing), stress, efficiency, editions
        )
        combined.issues.append(_experimental_issue(combined.citation))
        tree.add(combined)

        # --- CO-2 anchor bolts + base plate -----------------------------------
        bolt_circle = to_m(inputs.bolt_circle_diameter_mm)
        provided_area = to_base(inputs.provided_bolt_area_mm2, "mm**2", "area")
        bolt = column_calc.anchor_bolt_check(
            _value(governing),
            weight_n,
            bolt_circle,
            inputs.num_anchor_bolts,
            provided_area,
            to_base(inputs.allowable_bolt_tensile_mpa, "MPa", "stress"),
            editions,
        )
        bolt.issues.append(_experimental_issue(bolt.citation))
        tree.add(bolt)

        base_plate = column_calc.base_plate_thickness(
            to_base(inputs.foundation_bearing_pressure_kpa, "kPa", "pressure"),
            to_m(inputs.base_plate_projection_mm),
            to_base(inputs.allowable_base_plate_bending_mpa, "MPa", "stress"),
            editions,
        )
        base_plate.issues.append(_experimental_issue(base_plate.citation))
        tree.add(base_plate)

        # --- top-level experimental status (VAL-2) ----------------------------
        tree.add(self._status(editions))

        for result in tree.flatten():
            result.verification = VerificationStatus.EXPERIMENTAL
        return tree

    @staticmethod
    def _status(editions) -> Result:
        citation = citation_of(ASCE_7, "27.3 wind loads", editions, "S8")
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
            "CO-1..CO-3 combine single-load simplifications and are not validated against "
            "worked examples in v1.5 (VAL-2)."
        ),
        citation=citation,
    )


def _value(result: Result) -> float:
    if result.value is None:
        raise ValueError(f"calculation {result.symbol!r} produced no numeric value")
    return result.value
