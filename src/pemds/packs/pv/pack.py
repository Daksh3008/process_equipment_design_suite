"""Pressure-vessel pack orchestration (FR-PV, PV-1..PV-4).

Sizes a cylindrical vessel with two heads, determines the governing MAWP, checks
the UG-16 minimum, and computes the hydrostatic test pressure. The pack converts
user units to internal SI at this boundary and performs no I/O.

Thickness bases used:
* required nominal plate = pressure thickness (max of UG-16 floor and UG-27)
  + corrosion allowance + mill undertolerance;
* MAWP and the UG-16 check use the as-built metal thickness, i.e. the provided
  nominal plate minus the mill undertolerance and the corrosion allowance.
"""

from __future__ import annotations

import math

from pydantic import BaseModel

from ...calc import flat as flat_calc
from ...calc import heads as head_calc
from ...calc import hydrotest, joints, minimums, weights
from ...calc import mawp as mawp_calc
from ...calc import openings as openings_calc
from ...calc import shell as shell_calc
from ...calc.common import make_result, margin_verdict, propagate_experimental_children
from ...core.calc import CalcContext
from ...core.loadcase import LoadCase, LoadCaseSet
from ...core.provenance import Citation, VerificationStatus
from ...core.result import Issue, Result, ResultTree, Severity
from ...core.units import format_value, to_base
from ...core.validation import IssueCollector
from .model import VesselInputs


class PressureVesselPack:
    """The pressure-vessel equipment pack."""

    family = "pressure_vessel"
    Input = VesselInputs
    def validate(self, inputs: BaseModel) -> list[Issue]:
        if not isinstance(inputs, VesselInputs):
            raise TypeError(f"expected VesselInputs, got {type(inputs).__name__}")
        collector = IssueCollector()
        if inputs.fluid_component_key:
            from ...data.components import default_components

            try:
                default_components().get(inputs.fluid_component_key)
            except KeyError:
                collector.error(
                    f"unknown fluid component {inputs.fluid_component_key!r}",
                    field="fluid_component_key",
                    rationale="Choose a key from the bundled component database (CC-1).",
                )
        if inputs.inside_diameter_mm <= 0:
            collector.error("inside diameter must be > 0", field="inside_diameter_mm")
        if inputs.tangent_to_tangent_mm <= 0:
            collector.error(
                "tangent-to-tangent length must be > 0", field="tangent_to_tangent_mm"
            )
        if inputs.head_type == "torispherical":
            crown = inputs.torispherical_crown_radius_mm
            if crown is not None and crown < inputs.inside_diameter_mm:
                collector.error(
                    "torispherical crown radius must be >= inside diameter",
                    field="torispherical_crown_radius_mm",
                )
        if inputs.head_type == "flat" and not 0.0 < inputs.flat_head_factor_c < 1.0:
            collector.error(
                "flat-head factor C must be between 0 and 1",
                field="flat_head_factor_c",
            )
        for name, value in (
            ("design_temperature_c", inputs.design_temperature_c),
        ):
            if not math.isfinite(value):
                collector.error(f"{name} must be finite", field=name)
        if inputs.load_cases and not any(case.kind != "test" for case in inputs.load_cases):
            collector.error(
                "at least one non-test load case is required to govern pressure design",
                field="load_cases",
            )
        if inputs.support_type == "skirt" and inputs.support_height_mm <= 0:
            collector.error(
                "support height must be > 0 when the support type is skirt",
                field="support_height_mm",
            )
        if inputs.support_type == "skirt" and inputs.orientation != "vertical":
            collector.warning(
                "a skirt support is unusual on a horizontal vessel; a saddle is not "
                "modelled in v0.5",
                field="support_type",
                rationale="PV-1 support selection covers skirts in v0.5; saddles are deferred.",
            )
        for nozzle in inputs.nozzles:
            if not nozzle.tag.strip():
                collector.error("nozzle tag must not be blank", field="nozzles")
            if not 0.0 <= nozzle.elevation_mm <= inputs.tangent_to_tangent_mm:
                collector.error(
                    f"nozzle {nozzle.tag}: elevation must lie within 0..tangent-to-tangent "
                    f"({inputs.tangent_to_tangent_mm:g} mm)",
                    field="nozzles",
                )
            if (
                nozzle.provided_neck_thickness_mm is not None
                and 2.0 * nozzle.provided_neck_thickness_mm >= nozzle.outside_diameter_mm
            ):
                collector.error(
                    f"nozzle {nozzle.tag}: provided neck thickness must be below half the "
                    "outside diameter so a bore remains",
                    field="nozzles",
                )
        addition = inputs.corrosion_allowance_mm + inputs.mill_undertolerance_mm
        for field, provided in (
            ("provided_shell_thickness_mm", inputs.provided_shell_thickness_mm),
            ("provided_head_thickness_mm", inputs.provided_head_thickness_mm),
        ):
            if provided is not None and provided <= addition:
                collector.error(
                    "provided thickness must exceed corrosion allowance + mill undertolerance "
                    f"({addition:g} mm)",
                    field=field,
                )
        return collector.issues

    def calculate(self, inputs: BaseModel, ctx: CalcContext) -> ResultTree:
        if not isinstance(inputs, VesselInputs):
            raise TypeError(f"expected VesselInputs, got {type(inputs).__name__}")
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
        temperature = inputs.design_temperature_c
        governing_case_name = "design"
        if inputs.load_cases:
            cases = LoadCaseSet(
                [
                    LoadCase(
                        name=case.name,
                        pressure_pa=to_base(case.pressure_mpa, "MPa", "pressure"),
                        temperature_c=case.temperature_c,
                        kind=case.kind,
                    )
                    for case in inputs.load_cases
                ]
            )
            governing = cases.governing_internal()
            pressure = governing.pressure_pa
            temperature = governing.temperature_c
            governing_case_name = governing.name
        corrosion = to_m(inputs.corrosion_allowance_mm)
        mill = to_m(inputs.mill_undertolerance_mm)

        # UW-12 joint efficiency is looked up, never taken from a free numeric field.
        efficiency_result = joints.joint_efficiency(inputs.joint_type, inputs.radiography, editions)
        efficiency = _value(efficiency_result)

        shell_material = ctx.materials.get(inputs.material_key)
        head_material = ctx.materials.get(inputs.head_material_key)
        shell_stress = shell_material.allowable_stress_at(temperature)
        head_stress = head_material.allowable_stress_at(temperature)
        data_warnings = [
            *efficiency_result.issues,
            *_material_warnings(shell_material, head_material),
        ]
        data_status = (
            VerificationStatus.EXPERIMENTAL if data_warnings else VerificationStatus.VERIFIED
        )

        minimum = minimums.minimum_shell_thickness(editions)

        tree = ResultTree(name=inputs.tag, governing_case=governing_case_name)

        # --- fluid design case (FR-CC CC-3/CC-4): optional component-driven fill ----
        liquid_density = inputs.liquid_density_kg_m3
        fluid_result: Result | None = None
        if inputs.fluid_component_key:
            from ...data.compatibility import compatibility_warnings
            from ...data.components import default_components
            from ...data.fluid_properties import design_case

            case = design_case(
                inputs.fluid_component_key,
                temperature,
                pressure,
                editions,
                db=default_components(),
            )
            basis = case.design_basis()
            evaluated_density = basis["density_kg_m3"]
            if isinstance(evaluated_density, (int, float)):
                liquid_density = float(evaluated_density)
            fluid_result = make_result(
                symbol="fluid",
                value=liquid_density,
                kind="density",
                formula="rho = rho(fluid, T, P) from the chemical component database",
                substitutions={
                    "component": case.component.name,
                    "CAS": case.component.cas or "n/a",
                    "phase": case.phase.value,
                    "evaluated at": f"{temperature:g} degC",
                },
                citation=case.properties["rho"].citation,
                inputs_used=[
                    "fluid_component_key",
                    "design_temperature_c",
                    "design_pressure_mpa",
                ],
                children=list(case.properties.values()),
            )
            fluid_result.issues.extend(
                compatibility_warnings(case.component, shell_material, temperature, editions)
            )
            tree.add(fluid_result)

        # --- cylindrical shell -------------------------------------------------
        circumferential = shell_calc.circumferential_thickness(
            pressure, radius, shell_stress, efficiency, editions, corrosion
        )
        longitudinal = shell_calc.longitudinal_thickness(
            pressure, radius, shell_stress, efficiency, editions, corrosion
        )
        circ_pressure = _value(circumferential) - corrosion
        long_pressure = _value(longitudinal) - corrosion
        # UG-16 floors the metal thickness; CA and mill then add on top.
        minimum_metal = _value(minimum)
        required_metal = max(circ_pressure, long_pressure, minimum_metal)
        nominal_shell = required_metal + corrosion + mill
        shell_result = make_result(
            symbol="t_shell",
            value=nominal_shell,
            kind="length",
            formula=(
                "t_shell = max(UG-27(c)(1), UG-27(c)(2), UG-16 min) "
                "+ corrosion allowance + mill undertolerance"
            ),
            substitutions={
                "pressure thickness": format_value(max(circ_pressure, long_pressure), "m"),
                "UG-16 minimum": format_value(minimum_metal, "m"),
                "corrosion allowance": format_value(corrosion, "m"),
                "mill undertolerance": format_value(mill, "m"),
                "allowable stress S": format_value(shell_stress, "Pa"),
                "joint efficiency E": f"{efficiency:g}",
            },
            citation=circumferential.citation,
            inputs_used=[
                "design_pressure_mpa",
                "inside_diameter_mm",
                "material_key",
                "joint_type",
                "radiography",
                "corrosion_allowance_mm",
                "mill_undertolerance_mm",
                "provided_shell_thickness_mm",
            ],
            children=[circumferential, longitudinal],
            issues=data_warnings,
            verification=data_status,
        )
        if inputs.provided_shell_thickness_mm is not None:
            provided = to_m(inputs.provided_shell_thickness_mm)
            shell_result.verdict, shell_result.margin = margin_verdict(provided, nominal_shell)
            shell_result.substitutions["provided"] = format_value(provided, "m")
        tree.add(shell_result)

        # --- heads -------------------------------------------------------------
        head_result, head_mawp, head_metal = self._head(
            inputs, pressure, diameter, radius, head_stress, efficiency, corrosion, mill, minimum_metal, editions
        )
        head_result.issues.extend(data_warnings)
        head_result.verification = data_status
        tree.add(head_result)

        # --- MAWP (UG-98) ------------------------------------------------------
        shell_metal = _as_built_metal(
            inputs.provided_shell_thickness_mm, mill, corrosion, required_metal, to_m
        )
        mawp_circ = shell_calc.circumferential_mawp(
            shell_metal, radius, shell_stress, efficiency, editions
        )
        mawp_long = shell_calc.longitudinal_mawp(
            shell_metal, radius, shell_stress, efficiency, editions
        )
        governing = mawp_calc.governing_mawp(
            {
                "shell (circumferential)": _value(mawp_circ),
                "shell (longitudinal)": _value(mawp_long),
                "head": _value(head_mawp),
            },
            editions,
        )
        governing.verdict, governing.margin = margin_verdict(_value(governing), pressure)
        governing.verification = data_status
        governing.issues = data_warnings
        governing.children = [mawp_circ, mawp_long, head_mawp]
        tree.add(governing)

        # --- UG-16 minimum thickness ------------------------------------------
        minimum.verdict, minimum.margin = margin_verdict(shell_metal, minimum_metal)
        tree.add(minimum)

        # --- hydrostatic test (UG-99) -----------------------------------------
        # Test temperature input was removed in v1.5: the test pressure uses the
        # conservative S_T = S case, i.e. P_T = 1.3 * MAWP.
        test = hydrotest.hydrostatic_test_pressure(
            _value(governing), shell_stress, shell_stress, editions
        )
        test.verification = data_status  # derived from the same (possibly provisional) data
        test.issues = data_warnings
        tree.add(test)

        # --- weights (PV-4, UG-22) --------------------------------------------
        shell_length = to_m(inputs.tangent_to_tangent_mm)
        empty = weights.vessel_metal_mass(
            diameter, shell_length, shell_metal, head_metal, inputs.head_type,
            shell_material.density_kg_m3, editions,
        )
        liquid = weights.liquid_fill_mass(
            diameter, shell_length, inputs.head_type, liquid_density, editions,
        )
        operating = weights.operating_weight(_value(empty), _value(liquid), editions)
        water = weights.liquid_fill_mass(diameter, shell_length, inputs.head_type, 1000.0, editions)
        test_weight = weights.operating_weight(_value(empty), _value(water), editions)
        test_weight.symbol = "W_test"
        test_weight.formula = "W_test = W_empty + W_water"
        test_weight.substitutions["W_water"] = format_value(_value(water), "kg")
        cg = weights.centre_of_gravity_height(
            shell_length, weights.head_depth_m(inputs.head_type, diameter), editions,
        )
        for result in (empty, operating, test_weight):
            result.verification = data_status  # density comes from the material data
            result.issues = data_warnings
        for result in (empty, liquid, operating, test_weight, cg):
            tree.add(result)

        # --- nozzle schedule (PV-3): UG-37 area replacement per opening -------------
        tr_pressure = max(circ_pressure, long_pressure)
        for nozzle in sorted(inputs.nozzles, key=lambda n: (n.elevation_mm, n.tag)):
            tree.add(
                self._nozzle(
                    nozzle,
                    pressure,
                    shell_stress,
                    efficiency,
                    corrosion,
                    mill,
                    shell_metal,
                    tr_pressure,
                    editions,
                )
            )

        if data_status is VerificationStatus.EXPERIMENTAL:
            propagate_experimental_children(tree)
        return tree

    def _head(
        self,
        inputs: VesselInputs,
        pressure: float,
        diameter: float,
        radius: float,
        stress: float,
        efficiency: float,
        corrosion: float,
        mill: float,
        minimum_metal: float,
        editions,
    ) -> tuple[Result, Result, float]:
        crown = _crown_radius(inputs, diameter)
        thickness = self._head_thickness(
            inputs, pressure, diameter, radius, crown, stress, efficiency, corrosion, editions
        )
        head_pressure = _value(thickness) - corrosion
        required_metal = max(head_pressure, minimum_metal)
        nominal = required_metal + corrosion + mill
        wrapper = make_result(
            symbol="t_head",
            value=nominal,
            kind="length",
            formula=f"t_head = max(UG-32 {inputs.head_type}, UG-16 min) + CA + mill undertolerance",
            substitutions={
                "pressure thickness": format_value(head_pressure, "m"),
                "UG-16 minimum": format_value(minimum_metal, "m"),
                "corrosion allowance": format_value(corrosion, "m"),
                "mill undertolerance": format_value(mill, "m"),
            },
            citation=thickness.citation,
            inputs_used=["head_type", "design_pressure_mpa", "head_material_key"],
            children=[thickness],
        )
        head_metal = _as_built_metal(
            inputs.provided_head_thickness_mm,
            mill,
            corrosion,
            required_metal,
            lambda value: to_base(value, "mm", "length"),
        )
        if inputs.provided_head_thickness_mm is not None:
            provided = to_base(inputs.provided_head_thickness_mm, "mm", "length")
            wrapper.verdict, wrapper.margin = margin_verdict(provided, nominal)
            wrapper.substitutions["provided"] = format_value(provided, "m")

        mawp = self._head_mawp(
            inputs, head_metal, diameter, radius, crown, stress, efficiency, editions
        )
        return wrapper, mawp, head_metal

    def _head_thickness(
        self, inputs, pressure, diameter, radius, crown, stress, efficiency, corrosion, editions
    ) -> Result:
        head_type = inputs.head_type
        if head_type == "ellipsoidal":
            return head_calc.ellipsoidal_thickness(
                pressure, diameter, stress, efficiency, editions, corrosion
            )
        if head_type == "torispherical":
            return head_calc.torispherical_thickness(
                pressure, crown, stress, efficiency, editions, corrosion
            )
        if head_type == "hemispherical":
            return head_calc.hemispherical_thickness(
                pressure, radius, stress, efficiency, editions, corrosion
            )
        if head_type == "flat":
            return flat_calc.flat_head_thickness(
                pressure, diameter, inputs.flat_head_factor_c, stress, efficiency, editions, corrosion
            )
        raise ValueError(f"unsupported head type {head_type!r}")  # pragma: no cover

    def _head_mawp(
        self, inputs, metal, diameter, radius, crown, stress, efficiency, editions
    ) -> Result:
        head_type = inputs.head_type
        if head_type == "ellipsoidal":
            return head_calc.ellipsoidal_mawp(metal, diameter, stress, efficiency, editions)
        if head_type == "torispherical":
            return head_calc.torispherical_mawp(metal, crown, stress, efficiency, editions)
        if head_type == "hemispherical":
            return head_calc.hemispherical_mawp(metal, radius, stress, efficiency, editions)
        if head_type == "flat":
            return flat_calc.flat_head_mawp(
                metal, diameter, inputs.flat_head_factor_c, stress, efficiency, editions
            )
        raise ValueError(f"unsupported head type {head_type!r}")  # pragma: no cover

    def _nozzle(
        self,
        nozzle,
        pressure: float,
        stress: float,
        efficiency: float,
        corrosion: float,
        mill: float,
        shell_metal: float,
        tr_shell: float,
        editions,
    ) -> Result:
        """Area-replacement reinforcement check for one opening (PV-3, UG-37). EXPERIMENTAL.

        The opening diameter is ``OD - 2*t_actual`` when a neck thickness is
        provided, else ``OD`` (the conservative opening). Shell and nozzle excess
        are clamped at zero so an undersized component conservatively earns no
        reinforcement credit instead of raising into the whole vessel run.
        """
        to_m = lambda value: to_base(value, "mm", "length")
        od = to_m(nozzle.outside_diameter_mm)
        neck = (
            to_m(nozzle.provided_neck_thickness_mm)
            if nozzle.provided_neck_thickness_mm is not None
            else None
        )
        opening = od - 2.0 * neck if neck is not None else od
        if opening <= 0:  # pragma: no cover - validation blocks this before calculate
            raise ValueError(
                f"nozzle {nozzle.tag!r}: provided neck thickness leaves no bore"
            )
        excess_shell = max(0.0, shell_metal - tr_shell)

        neck_required = openings_calc.nozzle_neck_thickness(
            pressure, opening / 2.0, stress, efficiency, editions, corrosion
        )
        neck_pressure = _value(neck_required) - corrosion
        excess_nozzle = max(0.0, neck - corrosion - neck_pressure) if neck is not None else 0.0
        projection = to_m(nozzle.projection_mm)

        required = openings_calc.required_reinforcement_area(opening, tr_shell, editions)
        check = openings_calc.nozzle_reinforcement_check(
            opening, tr_shell, excess_shell, excess_nozzle, projection, editions
        )
        return make_result(
            symbol=f"nozzle_{nozzle.tag}",
            value=_value(check),
            kind="area",
            formula="A_avail >= A (simplified UG-37 area replacement)",
            substitutions={
                "d (opening)": format_value(opening, "m"),
                "tr (shell)": format_value(tr_shell, "m"),
                "A1 (shell)": check.substitutions["A1 (shell)"],
                "A2 (nozzle)": check.substitutions["A2 (nozzle)"],
                "projection": format_value(projection, "m"),
            },
            citation=check.citation,
            inputs_used=[
                "nozzles",
                "outside_diameter_mm",
                "provided_neck_thickness_mm",
                "projection_mm",
                "design_pressure_mpa",
                "inside_diameter_mm",
                "material_key",
                "joint_type",
                "radiography",
                "corrosion_allowance_mm",
                "mill_undertolerance_mm",
                "provided_shell_thickness_mm",
            ],
            verdict=check.verdict,
            margin=check.margin,
            verification=VerificationStatus.EXPERIMENTAL,
            children=[neck_required, required, check],
            issues=list(check.issues),
        )


def _crown_radius(inputs: VesselInputs, diameter: float) -> float:
    if inputs.torispherical_crown_radius_mm is not None:
        return to_base(inputs.torispherical_crown_radius_mm, "mm", "length")
    return diameter


def _as_built_metal(
    provided_mm: float | None, mill: float, corrosion: float, fallback: float, to_m
) -> float:
    if provided_mm is None:
        return fallback
    metal = to_m(provided_mm) - mill - corrosion
    if metal <= 0:
        raise ValueError(
            f"provided thickness {provided_mm} mm leaves no metal after mill undertolerance "
            f"{mill} m and corrosion allowance {corrosion} m"
        )
    return metal


def _value(result: Result) -> float:
    """Return a result's numeric value, failing loudly if it produced none."""
    if result.value is None:
        raise ValueError(f"calculation {result.symbol!r} produced no numeric value")
    return result.value


def _material_warnings(shell, head) -> list[Issue]:
    issues: list[Issue] = []
    seen: set[str] = set()
    for material, field in ((shell, "material_key"), (head, "head_material_key")):
        if material.key in seen:
            continue
        seen.add(material.key)
        if "UNVERIFIED" in material.provenance.checked_by.upper():
            issues.append(
                Issue(
                    severity=Severity.WARNING,
                    message=(
                        f"Material data for {material.key} is provisional "
                        f"({material.provenance.checked_by})."
                    ),
                    field=field,
                    rationale=(
                        "Data policy: unreviewed material data must not back a verified result."
                    ),
                    citation=Citation(
                        material.provenance.source,
                        material.provenance.edition,
                        material.provenance.clause,
                        material.provenance.source_tag,
                    ),
                )
            )
    return issues
