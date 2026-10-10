"""API 610-style pump datasheet rows (PU-14).

``pump_datasheet_rows`` assembles ``(label, value)`` rows from the pump inputs
and the calculated :class:`ResultTree`. The generic report engine can render the
rows directly; nothing here reproduces standard text, only the entered values and
our own results with their clauses.
"""

from __future__ import annotations

from ...core.result import Result, ResultTree
from ...core.units import UnitSystem, display_unit, format_value, from_base
from .model import PumpInputs


def _display(result: Result) -> str:
    """Render a result value in SI display units (mm, MPa, kW, ...)."""
    if result.value is None:
        return "-"
    if result.kind == "dimensionless":
        return format_value(result.value, result.unit)
    shown = from_base(result.value, result.kind, UnitSystem.SI)
    return format_value(shown, display_unit(result.kind, UnitSystem.SI))


def _find(tree: ResultTree, symbol: str) -> Result | None:
    for result in tree.flatten():
        if result.symbol == symbol:
            return result
    return None


def _value_of(tree: ResultTree, symbol: str) -> str:
    result = _find(tree, symbol)
    return _display(result) if result is not None else "-"


def _sub(tree: ResultTree, symbol: str, key: str) -> str:
    result = _find(tree, symbol)
    return result.substitutions.get(key, "-") if result is not None else "-"


def pump_datasheet_rows(inputs: PumpInputs, tree: ResultTree) -> list[tuple[str, str]]:
    """Assemble the completed pump datasheet as ordered (label, value) rows."""
    rows: list[tuple[str, str]] = []

    def section(title: str) -> None:
        rows.append((f"— {title} —", ""))

    def add(label: str, value: str) -> None:
        rows.append((label, str(value)))

    section("General")
    add("Equipment tag", inputs.tag)
    add("Service", inputs.service)
    add("Fluid", inputs.fluid_name)
    add("Flow", f"{inputs.flow_m3_h:g} m^3/h")
    add("Head", f"{inputs.head_m:g} m")
    add("Speed", f"{inputs.rated_speed_rpm:g} rpm" if inputs.rated_speed_rpm else "auto (selected)")
    add("Pumping temperature", f"{inputs.temperature_c:g} degC")
    add("Density", f"{inputs.density_kg_m3:g} kg/m^3")
    add("Viscosity", f"{inputs.viscosity_cp:g} cP")
    add("Vapour pressure", f"{inputs.vapour_pressure_kpa:g} kPa")
    add("NPSH available", f"{inputs.npsh_available_m:g} m")

    section("Hydraulics (PU-2..PU-6)")
    add("Specific speed Ns", _value_of(tree, "Ns"))
    add("Suction specific speed Nss", _value_of(tree, "Nss"))
    add("Impeller family", _sub(tree, "type_class", "impeller family"))
    add("API 610 type class (screening)", _sub(tree, "type_class", "API 610 type class (screening)"))
    add("Selected model", _sub(tree, "selection", "model"))
    add("Speed selected", _sub(tree, "selection", "speed"))
    add("Duty efficiency", _sub(tree, "selection", "duty efficiency"))
    add("% of BEP", _value_of(tree, "%BEP"))
    add("Preferred region", _sub(tree, "%BEP", "preferred region"))
    add("NPSHa", _value_of(tree, "NPSHa"))
    add("NPSH3", _sub(tree, "NPSHa", "NPSH3"))
    add("Hydraulic power", _value_of(tree, "P_hyd"))
    add("Absorbed power", _value_of(tree, "P_abs"))
    add("Driver rating", _value_of(tree, "P_motor"))
    add("Motor current", _value_of(tree, "I_motor"))

    section("Casing (PU-7)")
    add("Casing material", inputs.casing_material_key)
    add("Casing design pressure", f"{inputs.design_pressure_mpa:g} MPa")
    add("Required casing thickness", _value_of(tree, "t_casing"))
    add("Provided casing thickness", f"{inputs.provided_casing_thickness_mm:g} mm"
        if inputs.provided_casing_thickness_mm is not None else "-")
    add("Casing MAWP", _value_of(tree, "P_casing"))
    add("Casing test pressure", _value_of(tree, "P_T"))

    section("Shaft (PU-8)")
    add("Shaft diameter", f"{inputs.shaft_diameter_mm:g} mm")
    add("Bearing span", f"{inputs.shaft_bearing_span_mm:g} mm")
    add("Shaft torque", _value_of(tree, "T_shaft"))
    add("Shaft bending moment", _value_of(tree, "M_shaft"))
    add("Seal-chamber deflection", _value_of(tree, "delta_seal"))
    add("Deflection limit", f"{inputs.seal_chamber_deflection_limit_mm:g} mm")
    add("Equivalent shaft stress", _value_of(tree, "sigma_eq"))
    add("Shaft safety factor", _value_of(tree, "SF_shaft"))

    section("Bearings (PU-9)")
    add("Bearing type", inputs.bearing_type)
    add("Dynamic rating C", f"{inputs.radial_bearing_dynamic_load_n:g} N")
    add("Equivalent load P", f"{inputs.radial_bearing_load_n:g} N")
    add("L10 life", _value_of(tree, "L10h"))
    add("Minimum required", f"{inputs.min_bearing_life_h:g} h")

    section("Mechanical seal (PU-10)")
    add("Seal category", _sub(tree, "seal_arrangement", "category"))
    add("Seal arrangement", _sub(tree, "seal_arrangement", "arrangement"))
    add("Secondary containment", _sub(tree, "seal_arrangement", "containment"))
    add("Seal faces", _sub(tree, "seal_arrangement", "faces"))
    add("Flush plan", _sub(tree, "seal_arrangement", "flush plan"))

    section("Nozzle loads (PU-11)")
    if inputs.loads:
        for load in sorted(inputs.loads, key=lambda item: (item.service, item.tag)):
            result = _find(tree, f"nozzle_{load.tag}")
            verdict = result.verdict.value.upper() if result is not None else "-"
            add(f"{load.tag} ({load.service}) DN{load.size_mm:g}", f"interaction {_value_of(tree, f'nozzle_{load.tag}')} [{verdict}]")
    else:
        add("Nozzle loads", "none entered")

    section("Materials and vibration (PU-12, PU-13)")
    add("Material class (screening)", _sub(tree, "material_class", "material class (screening)"))
    add("NACE sour service", _sub(tree, "material_class", "NACE"))
    add("Vibration velocity", _value_of(tree, "v_rms"))
    add("Vibration limit", _sub(tree, "v_rms", "limit"))

    return rows
