"""Input model for the pressure-vessel pack (IN-1).

Fields are expressed in user-facing units (mm, MPa, degC) and converted to the
internal SI base at the pack boundary. Every field carries label, symbol, unit,
help text and the clause it feeds (IN-1).
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


class NozzleInput(BaseModel):
    """One nozzle / manway connection on the vessel shell (PV-3, UG-37)."""

    model_config = ConfigDict(extra="forbid")

    tag: str = _field(
        label="Nozzle tag",
        symbol="N",
        unit="",
        help_text="Identifier used on the report, drawing and 3D preview.",
        clause="n/a",
        default="N1",
    )
    outside_diameter_mm: float = _field(
        label="Outside diameter",
        symbol="d_N",
        unit="mm",
        help_text="Outside diameter of the nozzle neck (nominal pipe outer diameter).",
        clause="UG-37",
        gt=0,
    )
    provided_neck_thickness_mm: float | None = _field(
        label="Provided neck thickness",
        symbol="t_N",
        unit="mm",
        help_text="Nominal nozzle-neck wall thickness; if omitted, no A2 credit is taken.",
        clause="UG-45",
        default=None,
        gt=0,
    )
    projection_mm: float = _field(
        label="Projection",
        symbol="a",
        unit="mm",
        help_text="Outward nozzle projection from the shell outside face (A2 limit).",
        clause="UG-37",
        default=150.0,
        gt=0,
    )
    elevation_mm: float = _field(
        label="Elevation",
        symbol="z_N",
        unit="mm",
        help_text="Distance from the bottom tangent line to the nozzle centreline.",
        clause="UG-37",
        default=500.0,
        ge=0,
    )
    azimuth_deg: float = _field(
        label="Azimuth",
        symbol="az",
        unit="degree",
        help_text="Clockwise angle from the +X axis, 0 to 360, used on the 3D preview.",
        clause="n/a",
        default=0.0,
        ge=0,
        le=360,
    )
    service: str = _field(
        label="Service",
        symbol="svc",
        unit="",
        help_text="Service description shown as the drawing callout (e.g. 'process inlet').",
        clause="n/a",
        default="",
    )


class LoadCaseInput(BaseModel):
    """One design load case (CORE-7, UG-22)."""

    model_config = ConfigDict(extra="forbid")

    name: str = _field(
        label="Case name",
        symbol="case",
        unit="",
        help_text="Identifier for this load case (e.g. 'operating', 'test').",
        clause="UG-22",
        default="operating",
    )
    kind: Literal[
        "operating", "unused", "test", "wind", "seismic", "seismic+operating", "maintenance"
    ] = _field(
        label="Case kind",
        symbol="kind",
        unit="",
        help_text="Load-case category; the governing non-test case drives pressure design.",
        clause="UG-22",
        default="operating",
    )
    pressure_mpa: float = _field(
        label="Pressure",
        symbol="P",
        unit="MPa",
        help_text="Internal gauge pressure for this case.",
        clause="UG-21",
        ge=0.0,
    )
    temperature_c: float = _field(
        label="Temperature",
        symbol="T",
        unit="degC",
        help_text="Metal temperature for this case.",
        clause="UG-20",
    )


class VesselInputs(BaseModel):
    """Inputs required to size and verify a cylindrical pressure vessel."""

    model_config = ConfigDict(extra="forbid")

    tag: str = _field(
        label="Equipment tag",
        symbol="tag",
        unit="",
        help_text="Equipment identifier used on the report and drawing.",
        clause="n/a",
        default="V-101",
    )
    orientation: Literal["vertical", "horizontal"] = _field(
        label="Orientation",
        symbol="orientation",
        unit="",
        help_text="Vessel axis orientation; affects support and drawing only in v0.5.",
        clause="UG-22",
        default="vertical",
    )
    inside_diameter_mm: float = _field(
        label="Inside diameter",
        symbol="D",
        unit="mm",
        help_text="Inside diameter of the cylindrical shell.",
        clause="UG-27(c)",
        gt=0,
    )
    tangent_to_tangent_mm: float = _field(
        label="Tangent-to-tangent length",
        symbol="L",
        unit="mm",
        help_text="Cylindrical shell length between head tangent lines.",
        clause="UG-28(c)",
        gt=0,
    )
    material_key: str = _field(
        label="Shell material",
        symbol="mat",
        unit="",
        help_text="Material key from the materials database.",
        clause="ASME II-D",
    )
    head_material_key: str = _field(
        label="Head material",
        symbol="mat_h",
        unit="",
        help_text="Material key for the heads; usually the same as the shell.",
        clause="ASME II-D",
    )
    head_type: Literal["ellipsoidal", "torispherical", "hemispherical", "flat"] = _field(
        label="Head type",
        symbol="head",
        unit="",
        help_text="Formed head type.",
        clause="UG-32 / UG-34",
        default="ellipsoidal",
    )
    design_pressure_mpa: float = _field(
        label="Design pressure",
        symbol="P",
        unit="MPa",
        help_text="Internal design gauge pressure at the top of the vessel.",
        clause="UG-21",
        gt=0,
    )
    design_temperature_c: float = _field(
        label="Design temperature",
        symbol="T",
        unit="degC",
        help_text="Design metal temperature used to look up allowable stress.",
        clause="UG-20",
    )
    corrosion_allowance_mm: float = _field(
        label="Corrosion allowance",
        symbol="CA",
        unit="mm",
        help_text="Material added to the pressure thickness for corrosion/erosion.",
        clause="UG-25",
        default=0.0,
        ge=0.0,
    )
    mill_undertolerance_mm: float = _field(
        label="Mill undertolerance",
        symbol="mt",
        unit="mm",
        help_text="Plate mill undertolerance added to the required nominal thickness.",
        clause="UG-16",
        default=0.3,
        ge=0.0,
    )
    joint_type: str = _field(
        label="Joint type",
        symbol="joint",
        unit="",
        help_text="UW-12 joint type (e.g. '1' double-welded butt, '2' single-welded butt with backing).",
        clause="UW-12",
        default="1",
    )
    radiography: Literal["full", "spot", "none"] = _field(
        label="Radiography",
        symbol="RT",
        unit="",
        help_text="Extent of radiographic examination of the joint (UW-11).",
        clause="UW-11",
        default="full",
    )
    torispherical_crown_radius_mm: float | None = _field(
        label="Torispherical crown radius",
        symbol="L",
        unit="mm",
        help_text="Crown radius for a torispherical head; defaults to the inside diameter.",
        clause="UG-32(d)",
        default=None,
        gt=0.0,
    )
    flat_head_factor_c: float = _field(
        label="Flat-head factor C",
        symbol="C",
        unit="",
        help_text="UG-34 configuration factor for a flat head (0.13 to 0.33 typical).",
        clause="UG-34(c)(2)",
        default=0.33,
        gt=0.0,
    )
    provided_shell_thickness_mm: float | None = _field(
        label="Provided shell thickness",
        symbol="t_shell",
        unit="mm",
        help_text="Nominal shell plate thickness; if given, a pass/fail check is reported.",
        clause="UG-27(c)",
        default=None,
        gt=0.0,
    )
    provided_head_thickness_mm: float | None = _field(
        label="Provided head thickness",
        symbol="t_head",
        unit="mm",
        help_text="Nominal head thickness; if given, a pass/fail check is reported.",
        clause="UG-32",
        default=None,
        gt=0.0,
    )
    liquid_density_kg_m3: float = _field(
        label="Liquid density",
        symbol="rho_L",
        unit="kg/m^3",
        help_text="Density of the contained liquid, used for operating/test weights (PV-4).",
        clause="UG-22",
        default=1000.0,
        gt=0.0,
    )
    fluid_component_key: str | None = _field(
        label="Fluid component",
        symbol="comp",
        unit="",
        help_text=(
            "Optional key from the chemical component database (FR-CC). When set, the "
            "design case is evaluated at the design temperature and pressure, its liquid "
            "density drives the weights, and compatibility warnings are raised."
        ),
        clause="CC-3 / CC-4",
        default=None,
    )
    support_type: Literal["none", "skirt"] = _field(
        label="Support",
        symbol="support",
        unit="",
        help_text="Support shown on the drawing and 3D preview. Skirt is for vertical vessels.",
        clause="UG-22",
        default="none",
    )
    support_height_mm: float = _field(
        label="Support height",
        symbol="h_supp",
        unit="mm",
        help_text="Distance from the bottom head tangent line to the support base (skirt).",
        clause="UG-22",
        default=0.0,
        ge=0.0,
    )
    load_cases: list[LoadCaseInput] = Field(
        default_factory=list,
        json_schema_extra={
            "label": "Load cases",
            "symbol": "cases",
            "unit": "",
            "help": (
                "Optional load-case set. When provided, the governing non-test case drives "
                "pressure design and its name is reported (CORE-7, UG-22)."
            ),
            "clause": "UG-22",
        },
    )
    nozzles: list[NozzleInput] = Field(
        default_factory=list,
        json_schema_extra={
            "label": "Nozzle schedule",
            "symbol": "nozzles",
            "unit": "",
            "help": (
                "Connections whose UG-37 area-replacement reinforcement is checked. "
                "Elevation is measured from the bottom tangent line along the axis."
            ),
            "clause": "UG-37 / UG-45",
        },
    )
