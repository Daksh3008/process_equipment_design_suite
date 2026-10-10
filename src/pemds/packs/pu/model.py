"""Input model for the pump pack (PU-1).

Fields are expressed in user-facing units (m^3/h, m, MPa, degC, mm, cP, rpm) and
converted to the internal SI base at the pack boundary. Every field carries
label, symbol, unit, help text and the clause it feeds (IN-1). Fluid properties
are entered manually (DB-3 manual path) and flagged as user-entered; the pump
pack does not require the chemical component database.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def _field(
    *,
    label: str,
    symbol: str,
    unit: str,
    help_text: str,
    clause: str,
    default: Any = ...,
    gt: float | None = None,
    ge: float | None = None,
    le: float | None = None,
) -> Any:
    constraints: dict[str, Any] = {}
    if gt is not None:
        constraints["gt"] = gt
    if ge is not None:
        constraints["ge"] = ge
    if le is not None:
        constraints["le"] = le
    return Field(
        default,
        json_schema_extra={
            "label": label,
            "symbol": symbol,
            "unit": unit,
            "help": help_text,
            "clause": clause,
        },
        **constraints,
    )


class NozzleLoadInput(BaseModel):
    """One pump nozzle's entered forces, moments and allowables (PU-11)."""

    model_config = ConfigDict(extra="forbid")

    tag: str = _field(
        label="Nozzle tag",
        symbol="N",
        unit="",
        help_text="Identifier used on the report and drawing (e.g. 'suction', 'discharge').",
        clause="n/a",
        default="N1",
    )
    service: str = _field(
        label="Service",
        symbol="svc",
        unit="",
        help_text="Nozzle service description shown as the drawing callout.",
        clause="n/a",
        default="discharge",
    )
    size_mm: float = _field(
        label="Nominal size",
        symbol="DN",
        unit="mm",
        help_text="Nominal nozzle size, used for the drawing and datasheet.",
        clause="API 610",
        default=100.0,
        gt=0,
    )
    force_x_n: float = _field(
        label="Force X", symbol="Fx", unit="N",
        help_text="Applied nozzle force along the pump X axis.", clause="API 610",
        default=0.0,
    )
    force_y_n: float = _field(
        label="Force Y", symbol="Fy", unit="N",
        help_text="Applied nozzle force along the pump Y axis.", clause="API 610",
        default=0.0,
    )
    force_z_n: float = _field(
        label="Force Z", symbol="Fz", unit="N",
        help_text="Applied nozzle force along the pump Z axis.", clause="API 610",
        default=0.0,
    )
    moment_x_nm: float = _field(
        label="Moment X", symbol="Mx", unit="N*m",
        help_text="Applied nozzle moment about the pump X axis.", clause="API 610",
        default=0.0,
    )
    moment_y_nm: float = _field(
        label="Moment Y", symbol="My", unit="N*m",
        help_text="Applied nozzle moment about the pump Y axis.", clause="API 610",
        default=0.0,
    )
    moment_z_nm: float = _field(
        label="Moment Z", symbol="Mz", unit="N*m",
        help_text="Applied nozzle moment about the pump Z axis.", clause="API 610",
        default=0.0,
    )
    allowable_force_n: float = _field(
        label="Allowable force resultant", symbol="Fa", unit="N",
        help_text="API 610 allowable resultant force for this nozzle (entered).",
        clause="API 610",
        default=4000.0,
        gt=0,
    )
    allowable_moment_nm: float = _field(
        label="Allowable moment resultant", symbol="Ma", unit="N*m",
        help_text="API 610 allowable resultant moment for this nozzle (entered).",
        clause="API 610",
        default=3000.0,
        gt=0,
    )


class PumpInputs(BaseModel):
    """Duty point and mechanical data needed to select and verify a pump (PU-1)."""

    model_config = ConfigDict(extra="forbid")

    # --- identification and duty point ------------------------------------
    tag: str = _field(
        label="Equipment tag", symbol="tag", unit="",
        help_text="Equipment identifier used on the report and drawing.",
        clause="n/a", default="P-101",
    )
    service: str = _field(
        label="Service", symbol="service", unit="",
        help_text="Service description used for material and seal screening.",
        clause="PU-12", default="process water",
    )
    fluid_name: str = _field(
        label="Fluid", symbol="fluid", unit="",
        help_text="Pumped fluid name (user-entered fluid properties apply).",
        clause="DB-3", default="water",
    )
    flow_m3_h: float = _field(
        label="Flow", symbol="Q", unit="m^3/h",
        help_text="Duty volumetric flow rate.", clause="PU-1", gt=0,
    )
    head_m: float = _field(
        label="Head", symbol="H", unit="m",
        help_text="Duty total head rise.", clause="PU-1", gt=0,
    )
    rated_speed_rpm: float | None = _field(
        label="Rated speed", symbol="N", unit="rpm",
        help_text="Pump speed; leave blank to let the pack auto-select a screening speed.",
        clause="PU-2", default=None, gt=0,
    )
    density_kg_m3: float = _field(
        label="Density", symbol="rho", unit="kg/m^3",
        help_text="Fluid density at the duty temperature (user-entered, DB-3).",
        clause="PU-6", default=998.0, gt=0,
    )
    viscosity_cp: float = _field(
        label="Viscosity", symbol="mu", unit="cP",
        help_text="Fluid dynamic viscosity at the duty temperature (user-entered).",
        clause="PU-1", default=1.0, ge=0,
    )
    vapour_pressure_kpa: float = _field(
        label="Vapour pressure", symbol="Pv", unit="kPa",
        help_text="Fluid vapour pressure at the suction temperature (user-entered).",
        clause="PU-5", default=2.3, ge=0,
    )
    temperature_c: float = _field(
        label="Pumping temperature", symbol="T", unit="degC",
        help_text="Fluid temperature at the pump, used for material and seal screening.",
        clause="PU-12", default=25.0,
    )
    npsh_available_m: float = _field(
        label="NPSH available", symbol="NPSHa", unit="m",
        help_text="Net positive suction head available at the pump suction.",
        clause="PU-5", default=6.0, ge=0,
    )
    npshr_m: float | None = _field(
        label="NPSH required", symbol="NPSH3", unit="m",
        help_text="NPSH3 from the vendor curve; blank uses the catalogue value (sample data).",
        clause="PU-5", default=None, gt=0,
    )
    efficiency_pct: float | None = _field(
        label="Pump efficiency", symbol="eta", unit="%",
        help_text="Duty efficiency; blank uses the catalogue value (sample data).",
        clause="PU-6", default=None, gt=0, le=100,
    )

    # --- casing pressure design (PU-7) ------------------------------------
    design_pressure_mpa: float = _field(
        label="Casing design pressure", symbol="P", unit="MPa",
        help_text="Internal casing design gauge pressure.", clause="PU-7",
        default=2.0, gt=0,
    )
    casing_material_key: str = _field(
        label="Casing material", symbol="mat", unit="",
        help_text="Material key from the materials database.", clause="PU-7",
        default="SA-516-70",
    )
    casing_inside_radius_mm: float = _field(
        label="Casing inside radius", symbol="R", unit="mm",
        help_text="Inside radius of the pressure-retaining casing section.",
        clause="UG-27(c)(1)", default=150.0, gt=0,
    )
    corrosion_allowance_mm: float = _field(
        label="Corrosion allowance", symbol="CA", unit="mm",
        help_text="Metal added to the pressure thickness for corrosion/erosion.",
        clause="PU-12", default=3.0, ge=0,
    )
    joint_efficiency: float = _field(
        label="Joint efficiency", symbol="E", unit="",
        help_text="Longitudinal joint efficiency for the casing (seamless = 1.0).",
        clause="UW-12", default=1.0, gt=0, le=1.0,
    )
    provided_casing_thickness_mm: float | None = _field(
        label="Provided casing thickness", symbol="t", unit="mm",
        help_text="Supplied casing wall; if given, an MAWP pass/fail is reported.",
        clause="UG-27(c)(1)", default=20.0, gt=0,
    )

    # --- shaft (PU-8) ------------------------------------------------------
    shaft_diameter_mm: float = _field(
        label="Shaft diameter", symbol="d", unit="mm",
        help_text="Shaft diameter at the seal chamber.", clause="PU-8",
        default=30.0, gt=0,
    )
    shaft_bearing_span_mm: float = _field(
        label="Bearing span", symbol="L", unit="mm",
        help_text="Distance between bearing centres.", clause="PU-8",
        default=200.0, gt=0,
    )
    shaft_load_offset_mm: float = _field(
        label="Load offset", symbol="a", unit="mm",
        help_text="Distance from the drive-end bearing to the radial load (seal chamber).",
        clause="PU-8", default=100.0, gt=0,
    )
    shaft_radial_load_n: float = _field(
        label="Shaft radial load", symbol="F", unit="N",
        help_text="Radial load on the shaft at the impeller, used for bending and deflection.",
        clause="PU-8", default=500.0, ge=0,
    )

    # --- seal chamber and mechanical seal (PU-8, PU-10) -------------------
    seal_chamber_pressure_mpa: float = _field(
        label="Seal chamber pressure", symbol="P_sc", unit="MPa",
        help_text="Pressure at the seal chamber used for seal selection.",
        clause="PU-10", default=1.5, ge=0,
    )
    seal_chamber_inside_radius_mm: float = _field(
        label="Seal chamber inside radius", symbol="r_sc", unit="mm",
        help_text="Inside radius of the seal chamber (drawing and datasheet).",
        clause="PU-10", default=40.0, gt=0,
    )
    seal_chamber_deflection_limit_mm: float = _field(
        label="Seal chamber deflection limit", symbol="d_max", unit="mm",
        help_text="API 610 shaft deflection limit at the seal faces (default 0.05 mm).",
        clause="PU-8", default=0.05, gt=0,
    )
    seal_hazardous: bool = _field(
        label="Hazardous fluid", symbol="haz", unit="",
        help_text="True for toxic/flammable fluids that drive a dual seal arrangement.",
        clause="PU-10", default=False,
    )
    seal_solids: bool = _field(
        label="Solids present", symbol="solids", unit="",
        help_text="True when the fluid carries solids that need a clean flush plan.",
        clause="PU-10", default=False,
    )

    # --- bearings (PU-9) ---------------------------------------------------
    bearing_type: Literal["ball", "roller"] = _field(
        label="Bearing type", symbol="brg", unit="",
        help_text="Rolling bearing type; sets the ISO 281 life exponent.",
        clause="PU-9", default="ball",
    )
    radial_bearing_dynamic_load_n: float = _field(
        label="Radial bearing dynamic rating", symbol="C", unit="N",
        help_text="Basic dynamic load rating of the radial bearing (ISO 281).",
        clause="PU-9", default=80000.0, gt=0,
    )
    radial_bearing_load_n: float = _field(
        label="Radial bearing equivalent load", symbol="P", unit="N",
        help_text="Equivalent dynamic bearing load at rated conditions.",
        clause="PU-9", default=4000.0, gt=0,
    )
    min_bearing_life_h: float = _field(
        label="Minimum bearing life", symbol="L10min", unit="h",
        help_text="API 610 minimum required L10 life (default 25 000 h).",
        clause="PU-9", default=25000.0, gt=0,
    )

    # --- driver (PU-6) -----------------------------------------------------
    motor_margin: float = _field(
        label="Motor margin", symbol="k_m", unit="",
        help_text="Driver power margin over absorbed power (API 610 / NEMA, typ. 1.15).",
        clause="PU-6", default=1.15, ge=1.0,
    )
    motor_voltage_v: float = _field(
        label="Motor voltage", symbol="V", unit="V",
        help_text="Motor terminal voltage for the amp check.", clause="PU-6",
        default=400.0, gt=0,
    )
    motor_power_factor: float = _field(
        label="Motor power factor", symbol="pf", unit="",
        help_text="Motor power factor for the amp check.", clause="PU-6",
        default=0.86, gt=0, le=1.0,
    )
    motor_phases: int = _field(
        label="Motor phases", symbol="ph", unit="",
        help_text="Number of motor phases (1 or 3).", clause="PU-6",
        default=3, ge=1, le=3,
    )
    motor_fla_a: float | None = _field(
        label="Motor full-load amps", symbol="FLA", unit="A",
        help_text="Motor nameplate full-load current; if given, the amp check pass/fails.",
        clause="PU-6", default=None, gt=0,
    )

    # --- materials and vibration (PU-12, PU-13) ---------------------------
    chloride_ppm: float = _field(
        label="Chlorides", symbol="Cl-", unit="ppm",
        help_text="Chloride concentration for material-class screening.",
        clause="PU-12", default=0.0, ge=0,
    )
    h2s_present: bool = _field(
        label="H2S present", symbol="H2S", unit="",
        help_text="True for sour service; flags NACE MR0175 / ISO 15156.",
        clause="PU-12", default=False,
    )
    vibration_velocity_mm_s: float = _field(
        label="Vibration velocity", symbol="v_rms", unit="mm/s",
        help_text="Declared/measured overall vibration velocity, RMS.",
        clause="PU-13", default=2.0, ge=0,
    )

    # --- nozzle loads (PU-11) ---------------------------------------------
    loads: list[NozzleLoadInput] = Field(
        default_factory=list,
        json_schema_extra={
            "label": "Nozzle loads",
            "symbol": "loads",
            "unit": "",
            "help": (
                "Entered suction/discharge forces and moments with their API 610 "
                "allowables; each nozzle is checked for the force/moment interaction."
            ),
            "clause": "API 610",
        },
    )
