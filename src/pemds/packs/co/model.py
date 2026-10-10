"""Input model for the column / reactor pack (IN-1, FR-CO).

Fields are expressed in user-facing units (mm, MPa, kg, m/s, kPa) and converted
to the internal SI base at the pack boundary. Every field carries label, symbol,
unit, help text and the clause it feeds (IN-1).
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


class ColumnInputs(BaseModel):
    """Inputs to check a tall column/reactor shell, skirt and anchorage."""

    model_config = ConfigDict(extra="forbid")

    tag: str = _field(
        label="Equipment tag", symbol="tag", unit="",
        help_text="Column identifier used on the report and drawing.",
        clause="n/a", default="C-101",
    )
    inside_diameter_mm: float = _field(
        label="Inside diameter", symbol="D", unit="mm",
        help_text="Inside diameter of the cylindrical shell.",
        clause="UG-27(c)", gt=0,
    )
    tangent_to_tangent_mm: float = _field(
        label="Tangent-to-tangent length", symbol="L", unit="mm",
        help_text="Cylindrical shell length between head tangent lines.",
        clause="UG-27(c)", gt=0,
    )
    skirt_height_mm: float = _field(
        label="Skirt height", symbol="h_s", unit="mm",
        help_text="Distance from the base to the bottom tangent line, added to the wind-exposed height.",
        clause="CO-1", default=1500.0, ge=0.0,
    )
    material_key: str = _field(
        label="Shell material", symbol="mat", unit="",
        help_text="Material key from the materials database.",
        clause="ASME II-D",
    )
    design_pressure_mpa: float = _field(
        label="Design pressure", symbol="P", unit="MPa",
        help_text="Internal design gauge pressure at the top of the column.",
        clause="UG-21", gt=0,
    )
    design_temperature_c: float = _field(
        label="Design temperature", symbol="T", unit="degC",
        help_text="Design metal temperature used to look up allowable stress.",
        clause="UG-20", default=150.0,
    )
    joint_type: str = _field(
        label="Joint type", symbol="joint", unit="",
        help_text="UW-12 joint type (e.g. '1' double-welded butt).",
        clause="UW-12", default="1",
    )
    radiography: Literal["full", "spot", "none"] = _field(
        label="Radiography", symbol="RT", unit="",
        help_text="Extent of radiographic examination of the joint (UW-11).",
        clause="UW-11", default="full",
    )
    corrosion_allowance_mm: float = _field(
        label="Corrosion allowance", symbol="CA", unit="mm",
        help_text="Material added to the pressure thickness for corrosion/erosion.",
        clause="UG-25", default=0.0, ge=0.0,
    )
    mill_undertolerance_mm: float = _field(
        label="Mill undertolerance", symbol="mt", unit="mm",
        help_text="Plate mill undertolerance added to the required nominal thickness.",
        clause="UG-16", default=0.3, ge=0.0,
    )
    provided_shell_thickness_mm: float | None = _field(
        label="Provided shell thickness", symbol="t", unit="mm",
        help_text="Nominal shell plate thickness; if given, a pass/fail check is reported.",
        clause="UG-27(c)", default=None, gt=0,
    )
    operating_weight_kg: float = _field(
        label="Operating weight", symbol="W", unit="kg",
        help_text="Operating weight (metal + contents) used for seismic shear and overturning resistance.",
        clause="UG-22", default=50000.0, gt=0,
    )
    bolt_circle_diameter_mm: float = _field(
        label="Anchor bolt circle", symbol="D_b", unit="mm",
        help_text="Diameter of the anchor-bolt circle at the skirt base.",
        clause="CO-2", default=2200.0, gt=0,
    )
    num_anchor_bolts: int = _field(
        label="Number of anchor bolts", symbol="N", unit="",
        help_text="Total number of anchor bolts around the base.",
        clause="CO-2", default=12, gt=1,
    )
    provided_bolt_area_mm2: float = _field(
        label="Provided bolt root area", symbol="A_b", unit="mm^2",
        help_text="Root (tensile stress) area of one anchor bolt.",
        clause="CO-2", default=353.0, gt=0,
    )
    allowable_bolt_tensile_mpa: float = _field(
        label="Allowable bolt tensile stress", symbol="f_a", unit="MPa",
        help_text="Allowable tensile stress for the anchor-bolt material.",
        clause="CO-2", default=138.0, gt=0,
    )
    base_plate_projection_mm: float = _field(
        label="Base plate projection", symbol="l", unit="mm",
        help_text="Cantilever projection of the base plate beyond the shell.",
        clause="CO-2", default=60.0, gt=0,
    )
    foundation_bearing_pressure_kpa: float = _field(
        label="Foundation bearing pressure", symbol="p", unit="kPa",
        help_text="Bearing pressure under the base plate used to size its thickness.",
        clause="CO-2", default=3000.0, gt=0,
    )
    allowable_base_plate_bending_mpa: float = _field(
        label="Allowable base-plate bending stress", symbol="S_b", unit="MPa",
        help_text="Allowable bending stress for the base-plate material.",
        clause="CO-2", default=165.0, gt=0,
    )
    wind_speed_m_s: float = _field(
        label="Basic wind speed", symbol="V", unit="m/s",
        help_text="Basic (3-second gust) wind speed for the site.",
        clause="26.10 velocity pressure", default=45.0, gt=0,
    )
    exposure_factor_kz: float = _field(
        label="Velocity pressure exposure coefficient", symbol="Kz", unit="",
        help_text="ASCE 7 Kz at the reference height.",
        clause="26.10 velocity pressure", default=1.2, gt=0,
    )
    topographic_factor_kzt: float = _field(
        label="Topographic factor", symbol="Kzt", unit="",
        help_text="ASCE 7 topographic factor (1.0 for flat, unexposed terrain).",
        clause="26.10 velocity pressure", default=1.0, gt=0,
    )
    directionality_factor_kd: float = _field(
        label="Wind directionality factor", symbol="Kd", unit="",
        help_text="ASCE 7 directionality factor (0.85 for round shells).",
        clause="26.10 velocity pressure", default=0.85, gt=0, le=1.0,
    )
    seismic_cs: float = _field(
        label="Seismic response coefficient", symbol="Cs", unit="",
        help_text="ASCE 7 seismic response coefficient used for the base shear.",
        clause="12.8 equivalent lateral force", default=0.1, ge=0.0,
    )
