"""Heat-exchanger pack orchestration (FR-HX, HX-1..HX-3) — EXPERIMENTAL (VAL-2).

* HX-1 shell and channel/cover thickness reuse the ASME VIII-1 shell and head
  calculations.
* HX-2 tubesheet thickness uses the transparent TEMA-form expression, with the
  tube layout/ligament efficiency reported beside it and UHX flagged as the
  governing alternative.
* HX-3 checks the tube-to-tubesheet joint strength and notes the expansion-joint
  question.

Every result in the tree is EXPERIMENTAL and the governing shell and tubesheet
results carry a warning naming the experimental status (VAL-2).
"""

from __future__ import annotations

import math

from pydantic import BaseModel

from ...calc import flat as flat_calc
from ...calc import heads as head_calc
from ...calc import joints, minimums
from ...calc import shell as shell_calc
from ...calc import tubesheet as tubesheet_calc
from ...calc.common import make_result, margin_verdict
from ...core.calc import CalcContext, citation_of
from ...core.provenance import VerificationStatus
from ...core.result import Issue, Result, ResultTree, Severity, Verdict
from ...core.standards import TEMA
from ...core.units import format_value, to_base
from ...core.validation import IssueCollector
from .model import HeatExchangerInputs

_EXPERIMENTAL_MESSAGE = (
    "The heat-exchanger (HX) pack is EXPERIMENTAL in v1.5 (VAL-2); results must not "
    "be used for construction without independent verification."
)


class HeatExchangerPack:
    """The heat-exchanger equipment pack (TEMA + ASME VIII-1)."""

    family = "heat_exchanger"
    Input = HeatExchangerInputs

    def validate(self, inputs: BaseModel) -> list[Issue]:
        if not isinstance(inputs, HeatExchangerInputs):
            raise TypeError(f"expected HeatExchangerInputs, got {type(inputs).__name__}")
        collector = IssueCollector()
        if not math.isfinite(inputs.design_temperature_c):
            collector.error("design temperature must be finite", field="design_temperature_c")
        if inputs.tube_pitch_mm <= inputs.tube_outside_diameter_mm:
            collector.error(
                "tube pitch must exceed the tube outside diameter",
                field="tube_pitch_mm",
            )
        if 2.0 * inputs.tube_wall_thickness_mm >= inputs.tube_outside_diameter_mm:
            collector.error(
                "tube wall thickness must be below half the tube outside diameter",
                field="tube_wall_thickness_mm",
            )
        addition = inputs.corrosion_allowance_mm + inputs.mill_undertolerance_mm
        for field, provided in (
            ("provided_shell_thickness_mm", inputs.provided_shell_thickness_mm),
            ("provided_channel_thickness_mm", inputs.provided_channel_thickness_mm),
            ("provided_tubesheet_thickness_mm", inputs.provided_tubesheet_thickness_mm),
        ):
            if provided is not None and provided <= addition:
                collector.error(
                    "provided thickness must exceed corrosion allowance + mill undertolerance "
                    f"({addition:g} mm)",
                    field=field,
                )
        return collector.issues

    def calculate(self, inputs: BaseModel, ctx: CalcContext) -> ResultTree:
        if not isinstance(inputs, HeatExchangerInputs):
            raise TypeError(f"expected HeatExchangerInputs, got {type(inputs).__name__}")
        collector = IssueCollector()
        for issue in self.validate(inputs):
            if issue.severity is Severity.ERROR:
                collector.error(issue.message, issue.field)
        collector.raise_if_errors()

        editions = ctx.editions
        to_m = lambda value: to_base(value, "mm", "length")

        diameter = to_m(inputs.shell_inside_diameter_mm)
        radius = diameter / 2.0
        pressure = to_base(inputs.design_pressure_mpa, "MPa", "pressure")
        corrosion = to_m(inputs.corrosion_allowance_mm)
        mill = to_m(inputs.mill_undertolerance_mm)
        material = ctx.materials.get(inputs.material_key)
        stress = material.allowable_stress_at(inputs.design_temperature_c)

        efficiency_result = joints.joint_efficiency(inputs.joint_type, inputs.radiography, editions)
        efficiency = _value(efficiency_result)
        minimum_metal = _value(minimums.minimum_shell_thickness(editions))

        tree = ResultTree(name=inputs.tag, governing_case="design")

        # --- HX-1 shell (reuse VIII-1) ----------------------------------------
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
                "shell_inside_diameter_mm",
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
        if inputs.provided_shell_thickness_mm is not None:
            provided = to_m(inputs.provided_shell_thickness_mm)
            shell.verdict, shell.margin = margin_verdict(provided, nominal_shell)
            shell.substitutions["provided"] = format_value(provided, "m")
        tree.add(shell)

        # --- HX-1 channel / cover (reuse VIII-1) ------------------------------
        channel = self._channel(
            inputs, pressure, diameter, stress, efficiency, corrosion, mill, editions
        )
        channel.issues.append(_experimental_issue(channel.citation))
        tree.add(channel)

        # --- HX-2 tubesheet ---------------------------------------------------
        tubesheet = tubesheet_calc.tubesheet_thickness(
            to_m(inputs.effective_gasket_diameter_mm),
            pressure,
            stress,
            inputs.tubesheet_factor_f,
            editions,
            corrosion,
        )
        layout = tubesheet_calc.tube_layout(
            to_m(inputs.tube_outside_diameter_mm), to_m(inputs.tube_pitch_mm), editions
        )
        tubesheet.children.append(layout)
        tubesheet.issues.append(_experimental_issue(tubesheet.citation))
        nominal_tubesheet = _value(tubesheet) + mill
        if inputs.provided_tubesheet_thickness_mm is not None:
            provided = to_m(inputs.provided_tubesheet_thickness_mm)
            tubesheet.verdict, tubesheet.margin = margin_verdict(provided, nominal_tubesheet)
            tubesheet.substitutions["provided"] = format_value(provided, "m")
        tree.add(tubesheet)

        # --- HX-3 tube-to-tubesheet joint -------------------------------------
        joint = tubesheet_calc.tube_to_tubesheet_joint_check(
            to_m(inputs.tube_outside_diameter_mm),
            to_m(inputs.tube_wall_thickness_mm),
            pressure,
            inputs.tube_joint_type,
            to_base(inputs.tube_joint_shear_strength_mpa, "MPa", "stress"),
            editions,
            joint_length_m=to_m(inputs.tube_joint_length_mm),
            weld_leg_m=to_m(inputs.tube_weld_leg_mm),
        )
        joint.issues.append(_experimental_issue(joint.citation))
        if inputs.include_expansion_joint:
            joint.issues.append(
                Issue(
                    severity=Severity.WARNING,
                    message=(
                        "An expansion joint is provided; thermal-growth sizing (HX-5) is "
                        "still deferred in v1.5."
                    ),
                    rationale="This check does not credit the expansion joint's flexibility.",
                    citation=joint.citation,
                )
            )
        tree.add(joint)

        # --- top-level experimental status (VAL-2) ----------------------------
        tree.add(self._status(editions))

        for result in tree.flatten():
            result.verification = VerificationStatus.EXPERIMENTAL
        return tree

    def _channel(
        self,
        inputs: HeatExchangerInputs,
        pressure: float,
        diameter: float,
        stress: float,
        efficiency: float,
        corrosion: float,
        mill: float,
        editions,
    ) -> Result:
        cover = inputs.channel_cover_type
        if cover == "flat":
            thickness = flat_calc.flat_head_thickness(
                pressure, diameter, inputs.channel_flat_factor_c, stress, efficiency, editions, corrosion
            )
        elif cover == "ellipsoidal":
            thickness = head_calc.ellipsoidal_thickness(
                pressure, diameter, stress, efficiency, editions, corrosion
            )
        elif cover == "torispherical":
            thickness = head_calc.torispherical_thickness(
                pressure, diameter, stress, efficiency, editions, corrosion
            )
        else:  # hemispherical
            thickness = head_calc.hemispherical_thickness(
                pressure, diameter / 2.0, stress, efficiency, editions, corrosion
            )
        nominal = _value(thickness) + mill
        result = make_result(
            symbol="t_channel",
            value=nominal,
            kind="length",
            formula=f"t_channel = {cover} cover per VIII-1 + mill undertolerance",
            substitutions={
                "cover type": cover,
                "pressure thickness + CA": format_value(_value(thickness), "m"),
                "mill undertolerance": format_value(mill, "m"),
            },
            citation=thickness.citation,
            inputs_used=[
                "shell_inside_diameter_mm",
                "design_pressure_mpa",
                "channel_cover_type",
                "channel_flat_factor_c",
                "material_key",
                "provided_channel_thickness_mm",
            ],
            children=[thickness],
        )
        if inputs.provided_channel_thickness_mm is not None:
            provided = to_base(inputs.provided_channel_thickness_mm, "mm", "length")
            result.verdict, result.margin = margin_verdict(provided, nominal)
            result.substitutions["provided"] = format_value(provided, "m")
        return result

    @staticmethod
    def _status(editions) -> Result:
        citation = citation_of(TEMA, "R-6 tubesheet", editions, "S6")
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
            "HX-1..HX-3 build on a transparent TEMA subset and are not validated against "
            "worked examples in v1.5 (VAL-2)."
        ),
        citation=citation,
    )


def _value(result: Result) -> float:
    if result.value is None:
        raise ValueError(f"calculation {result.symbol!r} produced no numeric value")
    return result.value
