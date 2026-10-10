"""Pump pack orchestration (FR-PU, PU-1..PU-15).

Runs the pump calculations into a single :class:`ResultTree`. The pack converts
user units to internal SI at this boundary, loads the provenance-stamped generic
sample curve catalogue once and performs no other I/O.

Verification honesty (VAL-2): checks that depend on the sample catalogue
(selection/BEP, catalogue efficiency or NPSH3) or on a documented simplified
subset (type-class guidance, POR/AOR, seal selection, nozzle allowables,
material class) are marked EXPERIMENTAL with a warning. Casing results inherit
the material data's provisional flag exactly as the pressure-vessel pack does.
"""

from __future__ import annotations

import math
from functools import lru_cache

from pydantic import BaseModel

from ...calc import pump as pump_calc
from ...calc.common import margin_verdict, propagate_experimental_children
from ...calc.pump import PumpCurve
from ...core.calc import CalcContext
from ...core.provenance import VerificationStatus
from ...core.result import Issue, Result, ResultTree, Severity, Verdict
from ...core.units import format_value, to_base
from ...core.validation import IssueCollector
from ...data.loader import load_package_data
from .model import PumpInputs


@lru_cache(maxsize=1)
def _catalogue() -> tuple[PumpCurve, ...]:
    """Load and cache the provenance-stamped sample curve catalogue."""
    data_file = load_package_data("pumps/sample_curves.json")
    return pump_calc.catalogue_from_data(data_file.data)


class PumpPack:
    """The centrifugal pump equipment pack (API 610 / ISO 13709)."""

    family = "pump"
    Input = PumpInputs

    def validate(self, inputs: BaseModel) -> list[Issue]:
        if not isinstance(inputs, PumpInputs):
            raise TypeError(f"expected PumpInputs, got {type(inputs).__name__}")
        collector = IssueCollector()
        if inputs.flow_m3_h <= 0:
            collector.error("flow must be > 0", field="flow_m3_h")
        if inputs.head_m <= 0:
            collector.error("head must be > 0", field="head_m")
        if inputs.density_kg_m3 <= 0:
            collector.error("density must be > 0", field="density_kg_m3")
        if inputs.rated_speed_rpm is not None and inputs.rated_speed_rpm <= 0:
            collector.error("rated speed must be > 0 when given", field="rated_speed_rpm")
        if inputs.npsh_available_m < 0:
            collector.error("NPSH available must be >= 0", field="npsh_available_m")
        if not math.isfinite(inputs.temperature_c):
            collector.error("temperature must be finite", field="temperature_c")
        if inputs.shaft_load_offset_mm >= inputs.shaft_bearing_span_mm:
            collector.error(
                "shaft load offset must be below the bearing span",
                field="shaft_load_offset_mm",
            )
        if inputs.motor_phases not in (1, 3):
            collector.error("motor phases must be 1 or 3", field="motor_phases")
        addition = inputs.corrosion_allowance_mm
        provided = inputs.provided_casing_thickness_mm
        if provided is not None and provided <= addition:
            collector.error(
                "provided casing thickness must exceed the corrosion allowance",
                field="provided_casing_thickness_mm",
            )
        for load in inputs.loads:
            if not load.tag.strip():
                collector.error("nozzle load tag must not be blank", field="loads")
            if load.allowable_force_n <= 0 or load.allowable_moment_nm <= 0:
                collector.error(
                    f"nozzle {load.tag}: allowables must be > 0", field="loads"
                )
        return collector.issues

    def calculate(self, inputs: BaseModel, ctx: CalcContext) -> ResultTree:
        if not isinstance(inputs, PumpInputs):
            raise TypeError(f"expected PumpInputs, got {type(inputs).__name__}")
        collector = IssueCollector()
        for issue in self.validate(inputs):
            if issue.severity is Severity.ERROR:
                collector.error(issue.message, issue.field)
        collector.raise_if_errors()

        editions = ctx.editions
        flow = to_base(inputs.flow_m3_h, "m**3/h", "flow")
        head = to_base(inputs.head_m, "m", "length")
        density = to_base(inputs.density_kg_m3, "kg/m**3", "density")
        npsh_available = to_base(inputs.npsh_available_m, "m", "length")
        temperature = inputs.temperature_c
        pressure = to_base(inputs.design_pressure_mpa, "MPa", "pressure")
        radius = to_base(inputs.casing_inside_radius_mm, "mm", "length")
        corrosion = to_base(inputs.corrosion_allowance_mm, "mm", "length")
        seal_pressure = to_base(inputs.seal_chamber_pressure_mpa, "MPa", "pressure")
        shaft_diameter = to_base(inputs.shaft_diameter_mm, "mm", "length")
        span = to_base(inputs.shaft_bearing_span_mm, "mm", "length")
        offset = to_base(inputs.shaft_load_offset_mm, "mm", "length")
        deflection_limit = to_base(inputs.seal_chamber_deflection_limit_mm, "mm", "length")
        vibration = to_base(inputs.vibration_velocity_mm_s, "mm/s", "velocity")

        catalogue = _catalogue()
        candidates = pump_calc.rank_candidates(
            flow, head, catalogue, inputs.rated_speed_rpm
        )
        best = candidates[0] if candidates else None

        if inputs.rated_speed_rpm is not None:
            speed_rpm = inputs.rated_speed_rpm
        elif best is not None:
            speed_rpm = best.speed_rpm
        else:
            # Screening auto speed targeting a radial specific speed of 25.
            speed_rpm = 25.0 * head**0.75 / math.sqrt(flow)

        if inputs.npshr_m is not None:
            npshr = to_base(inputs.npshr_m, "m", "length")
            npsh_from_catalogue = False
        elif best is not None:
            npshr = best.npshr_m
            npsh_from_catalogue = True
        else:
            collector.error(
                "provide NPSH required, or a catalogue curve covering the duty flow",
                field="npshr_m",
            )
            collector.raise_if_errors()

        if inputs.efficiency_pct is not None:
            efficiency = inputs.efficiency_pct / 100.0
            efficiency_from_catalogue = False
        elif best is not None:
            efficiency = best.efficiency_pct / 100.0
            efficiency_from_catalogue = True
        else:
            collector.error(
                "provide pump efficiency, or a catalogue curve covering the duty flow",
                field="efficiency_pct",
            )
            collector.raise_if_errors()

        material = ctx.materials.get(inputs.casing_material_key)
        material_provisional = _is_provisional(material.provenance.checked_by)
        allowable_stress = material.allowable_stress_at(temperature)

        tree = ResultTree(name=inputs.tag, governing_case="rated")

        # --- PU-2 specific speed and type guidance ---------------------------
        ns_result = pump_calc.specific_speed(speed_rpm, flow, head, editions)
        nss_result = pump_calc.suction_specific_speed(speed_rpm, flow, npshr, editions)
        type_result = pump_calc.pump_type_classification(
            _value(ns_result), _value(nss_result), flow, editions
        )
        for result in (ns_result, nss_result, type_result):
            tree.add(result)

        # --- PU-3 selection and PU-4 operating region -----------------------
        selection = pump_calc.select_from_catalogue(
            flow, head, catalogue, editions, inputs.rated_speed_rpm
        )
        tree.add(selection)
        tree.add(
            pump_calc.operating_region_check(best.percent_bep if best else 0.0, editions)
        )

        # --- PU-5 NPSH -------------------------------------------------------
        npsh = pump_calc.npsh_check(npsh_available, npshr, editions)
        if npsh_from_catalogue:
            _mark_experimental(
                npsh,
                "NPSH check uses the catalogue NPSH3 (generic sample data).",
                "Data policy: unverified catalogue data must not back a verified result.",
            )
        tree.add(npsh)

        # --- PU-6 power and driver sizing ------------------------------------
        hydraulic = pump_calc.hydraulic_power(density, flow, head, editions)
        absorbed = pump_calc.absorbed_power(_value(hydraulic), efficiency, editions)
        driver = pump_calc.motor_sizing(
            _value(absorbed), editions, inputs.motor_margin
        )
        current = pump_calc.motor_current(
            _value(absorbed),
            inputs.motor_voltage_v,
            inputs.motor_power_factor,
            inputs.motor_phases,
            editions,
        )
        if inputs.motor_fla_a is not None:
            current.verdict = (
                Verdict.PASS if _value(current) <= inputs.motor_fla_a else Verdict.FAIL
            )
            current.margin = (inputs.motor_fla_a - _value(current)) / _value(current)
        if efficiency_from_catalogue:
            for result in (absorbed, driver, current):
                _mark_experimental(
                    result,
                    "Absorbed power and driver sizing use the catalogue duty efficiency "
                    "(generic sample data).",
                    "Data policy: unverified catalogue data must not back a verified result.",
                )
        for result in (hydraulic, absorbed, driver, current):
            tree.add(result)

        # --- PU-7 casing -----------------------------------------------------
        casing = pump_calc.casing_wall_thickness(
            pressure, radius, allowable_stress, inputs.joint_efficiency, editions, corrosion
        )
        casing.symbol = "t_casing"
        if inputs.provided_casing_thickness_mm is not None:
            provided_metal = to_base(inputs.provided_casing_thickness_mm, "mm", "length") - corrosion
            casing.verdict, casing.margin = margin_verdict(provided_metal, _value(casing))
            casing.substitutions["provided"] = format_value(
                to_base(inputs.provided_casing_thickness_mm, "mm", "length"), "m"
            )
            metal = provided_metal
        else:
            metal = _value(casing) - corrosion
        mawp = pump_calc.casing_mawp(
            metal, radius, allowable_stress, inputs.joint_efficiency, editions
        )
        mawp.symbol = "P_casing"
        mawp.verdict, mawp.margin = margin_verdict(_value(mawp), pressure)
        casing_test = pump_calc.casing_hydrotest_pressure(_value(mawp), editions)
        if material_provisional:
            note = Issue(
                severity=Severity.WARNING,
                message=(
                    f"Material data for {material.key} is provisional "
                    f"({material.provenance.checked_by})."
                ),
                rationale="Data policy: unreviewed material data must not back a verified result.",
            )
            for result in (casing, mawp, casing_test):
                _mark_experimental(result, note.message, note.rationale or "")
        for result in (casing, mawp, casing_test):
            tree.add(result)

        # --- PU-8 shaft ------------------------------------------------------
        omega = pump_calc.angular_speed_rad_s(speed_rpm)
        torque = pump_calc.shaft_torque(_value(absorbed), omega, editions)
        distance_b = span - offset
        moment = pump_calc.shaft_bending_moment(
            inputs.shaft_radial_load_n, offset, distance_b, editions
        )
        second_moment = math.pi * shaft_diameter**4 / 64.0
        deflection = pump_calc.seal_chamber_deflection(
            inputs.shaft_radial_load_n,
            offset,
            distance_b,
            material.modulus_at(temperature),
            second_moment,
            editions,
            deflection_limit,
        )
        stress = pump_calc.combined_shaft_stress(
            _value(moment), _value(torque), shaft_diameter, editions
        )
        safety = pump_calc.shaft_safety_factor(
            material.yield_strength_pa, _value(stress), editions
        )
        if efficiency_from_catalogue:
            for result in (torque, stress, safety):
                _mark_experimental(
                    result,
                    "Shaft torque and combined stress use the catalogue duty efficiency "
                    "(generic sample data).",
                    "Data policy: unverified catalogue data must not back a verified result.",
                )
        for result in (torque, moment, deflection, stress, safety):
            tree.add(result)

        # --- PU-9 bearing life ----------------------------------------------
        exponent = 3.0 if inputs.bearing_type == "ball" else 10.0 / 3.0
        bearing = pump_calc.bearing_life(
            inputs.radial_bearing_dynamic_load_n,
            inputs.radial_bearing_load_n,
            speed_rpm,
            editions,
            exponent=exponent,
            minimum_life_h=inputs.min_bearing_life_h,
        )
        tree.add(bearing)

        # --- PU-10 mechanical seal ------------------------------------------
        tree.add(
            pump_calc.seal_selection(
                temperature,
                seal_pressure,
                inputs.service,
                inputs.seal_hazardous,
                inputs.seal_solids,
                editions,
            )
        )

        # --- PU-11 nozzle loads ---------------------------------------------
        for load in sorted(inputs.loads, key=lambda item: (item.service, item.tag)):
            force = math.sqrt(load.force_x_n**2 + load.force_y_n**2 + load.force_z_n**2)
            moment_resultant = math.sqrt(
                load.moment_x_nm**2 + load.moment_y_nm**2 + load.moment_z_nm**2
            )
            result = pump_calc.nozzle_load_check(
                force,
                moment_resultant,
                load.allowable_force_n,
                load.allowable_moment_nm,
                editions,
            )
            result.symbol = f"nozzle_{load.tag}"
            result.substitutions["tag"] = load.tag
            result.substitutions["service"] = load.service
            tree.add(result)

        # --- PU-12 material class -------------------------------------------
        tree.add(
            pump_calc.material_class_selection(
                temperature,
                inputs.service,
                inputs.chloride_ppm,
                inputs.h2s_present,
                editions,
            )
        )

        # --- PU-13 vibration -------------------------------------------------
        tree.add(pump_calc.vibration_check(vibration, editions))

        propagate_experimental_children(tree)
        return tree


def _mark_experimental(result: Result, message: str, rationale: str) -> None:
    """Downgrade a result to EXPERIMENTAL and attach the disclosure warning."""
    result.verification = VerificationStatus.EXPERIMENTAL
    result.issues.append(
        Issue(severity=Severity.WARNING, message=message, rationale=rationale)
    )


def _is_provisional(checked_by: str) -> bool:
    return "UNVERIFIED" in checked_by.upper()


def _value(result: Result) -> float:
    if result.value is None:
        raise ValueError(f"calculation {result.symbol!r} produced no numeric value")
    return result.value
