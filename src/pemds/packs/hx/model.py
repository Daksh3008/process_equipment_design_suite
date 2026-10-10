"""Input model for the heat-exchanger pack (IN-1, FR-HX).

Fields are expressed in user-facing units (mm, MPa) and converted to the internal
SI base at the pack boundary. Every field carries label, symbol, unit, help text
and the clause it feeds (IN-1).
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


class HeatExchangerInputs(BaseModel):
    """Inputs to size and verify a shell-and-tube heat exchanger (TEMA)."""

    model_config = ConfigDict(extra="forbid")

    tag: str = _field(
        label="Equipment tag", symbol="tag", unit="",
        help_text="Exchanger identifier used on the report and drawing.",
        clause="n/a", default="E-101",
    )
    shell_inside_diameter_mm: float = _field(
        label="Shell inside diameter", symbol="D_s", unit="mm",
        help_text="Inside diameter of the shell and the channel.",
        clause="UG-27(c)", gt=0,
    )
    shell_tangent_to_tangent_mm: float = _field(
        label="Shell tangent-to-tangent length", symbol="L", unit="mm",
        help_text="Cylindrical shell length between head tangent lines.",
        clause="UG-27(c)", gt=0,
    )
    material_key: str = _field(
        label="Shell/channel material", symbol="mat", unit="",
        help_text="Material key from the materials database.",
        clause="ASME II-D",
    )
    design_pressure_mpa: float = _field(
        label="Design pressure", symbol="P", unit="MPa",
        help_text="Internal design gauge pressure for the shell and channel.",
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
        label="Provided shell thickness", symbol="t_s", unit="mm",
        help_text="Nominal shell plate thickness; if given, a pass/fail check is reported.",
        clause="UG-27(c)", default=None, gt=0,
    )
    channel_cover_type: Literal["flat", "ellipsoidal", "torispherical", "hemispherical"] = _field(
        label="Channel cover type", symbol="cover", unit="",
        help_text="Form of the channel cover / closure.",
        clause="UG-32 / UG-34", default="flat",
    )
    channel_flat_factor_c: float = _field(
        label="Flat cover factor C", symbol="C", unit="",
        help_text="UG-34 configuration factor for a flat channel cover.",
        clause="UG-34(c)(2)", default=0.33, gt=0, le=1.0,
    )
    provided_channel_thickness_mm: float | None = _field(
        label="Provided channel thickness", symbol="t_c", unit="mm",
        help_text="Nominal channel/cover thickness; if given, a pass/fail check is reported.",
        clause="UG-32", default=None, gt=0,
    )
    effective_gasket_diameter_mm: float = _field(
        label="Effective gasket diameter", symbol="G", unit="mm",
        help_text="Tubesheet effective gasket diameter used by the TEMA-form equation.",
        clause="R-6 tubesheet", gt=0,
    )
    tubesheet_factor_f: float = _field(
        label="Tubesheet factor F", symbol="F", unit="",
        help_text="Dimensionless tubesheet boundary-condition factor.",
        clause="R-6 tubesheet", default=1.0, gt=0,
    )
    provided_tubesheet_thickness_mm: float | None = _field(
        label="Provided tubesheet thickness", symbol="t_ts", unit="mm",
        help_text="Nominal tubesheet thickness; if given, a pass/fail check is reported.",
        clause="R-6 tubesheet", default=None, gt=0,
    )
    tube_outside_diameter_mm: float = _field(
        label="Tube outside diameter", symbol="d_o", unit="mm",
        help_text="Outside diameter of one tube.",
        clause="R-7.4 tube layout", gt=0,
    )
    tube_wall_thickness_mm: float = _field(
        label="Tube wall thickness", symbol="t_t", unit="mm",
        help_text="Nominal tube wall thickness.",
        clause="R-7.4 tube layout", gt=0,
    )
    tube_pitch_mm: float = _field(
        label="Tube pitch", symbol="p", unit="mm",
        help_text="Centre-to-centre tube spacing (must exceed the tube outside diameter).",
        clause="R-7.4 tube layout", gt=0,
    )
    tube_count: int = _field(
        label="Tube count", symbol="N_t", unit="",
        help_text="Number of tubes in the bundle (informational).",
        clause="R-7.4 tube layout", default=100, gt=1,
    )
    tube_joint_type: Literal["rolled", "welded"] = _field(
        label="Tube joint type", symbol="jt", unit="",
        help_text="Tube-to-tubesheet joint: rolled or welded.",
        clause="R-8 tube-to-tubesheet joint", default="rolled",
    )
    tube_joint_shear_strength_mpa: float = _field(
        label="Joint allowable shear", symbol="tau", unit="MPa",
        help_text="Allowable shear strength of the rolled or welded joint.",
        clause="R-8 tube-to-tubesheet joint", default=70.0, gt=0,
    )
    tube_joint_length_mm: float = _field(
        label="Rolled joint length", symbol="L_j", unit="mm",
        help_text="Engagement length of a rolled joint.",
        clause="R-8 tube-to-tubesheet joint", default=40.0, gt=0,
    )
    tube_weld_leg_mm: float = _field(
        label="Weld leg", symbol="w", unit="mm",
        help_text="Fillet-weld leg size for a welded joint.",
        clause="R-8 tube-to-tubesheet joint", default=3.0, gt=0,
    )
    include_expansion_joint: bool = _field(
        label="Expansion joint provided", symbol="ej", unit="",
        help_text="Whether an expansion joint / floating head is provided for tube growth.",
        clause="HX-3", default=False,
    )
