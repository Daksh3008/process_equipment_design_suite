"""Input model for the storage-tank pack (IN-1, FR-TK).

Fields are expressed in user-facing units (mm, kPa, m/s) and converted to the
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


class StorageTankInputs(BaseModel):
    """Inputs to size and verify an above-ground storage tank (API 650)."""

    model_config = ConfigDict(extra="forbid")

    tag: str = _field(
        label="Equipment tag", symbol="tag", unit="",
        help_text="Tank identifier used on the report and drawing.",
        clause="n/a", default="TK-101",
    )
    diameter_mm: float = _field(
        label="Tank diameter", symbol="D", unit="mm",
        help_text="Nominal inside diameter of the cylindrical shell.",
        clause="5.6 shell design", gt=0,
    )
    design_liquid_height_mm: float = _field(
        label="Design liquid height", symbol="H", unit="mm",
        help_text="Design liquid level above the shell bottom, used by the one-foot method.",
        clause="5.6 shell design", gt=0,
    )
    specific_gravity: float = _field(
        label="Liquid specific gravity", symbol="G", unit="",
        help_text="Design specific gravity of the stored liquid (water = 1.0).",
        clause="5.6 shell design", default=1.0, gt=0,
    )
    design_temperature_c: float = _field(
        label="Design temperature", symbol="T", unit="degC",
        help_text="Design metal temperature used to look up allowable stress.",
        clause="5.6 shell design", default=60.0,
    )
    material_key: str = _field(
        label="Shell material", symbol="mat", unit="",
        help_text="Material key from the materials database.",
        clause="ASME II-D",
    )
    joint_efficiency: float = _field(
        label="Joint efficiency", symbol="E", unit="",
        help_text="Shell joint efficiency for the courses being checked (1.0 fully radiographed).",
        clause="5.6 shell design", default=1.0, gt=0, le=1.0,
    )
    corrosion_allowance_mm: float = _field(
        label="Corrosion allowance", symbol="CA", unit="mm",
        help_text="Material added to the shell thickness for corrosion/erosion.",
        clause="5.6 shell design", default=0.0, ge=0.0,
    )
    provided_shell_thickness_mm: float | None = _field(
        label="Provided shell thickness", symbol="t", unit="mm",
        help_text="Nominal first-course plate thickness; if given, a pass/fail check is reported.",
        clause="5.6 shell design", default=None, gt=0,
    )
    plate_width_mm: float = _field(
        label="Plate width (course height)", symbol="w", unit="mm",
        help_text="Width of one shell plate; each course is one plate high.",
        clause="5.6 shell design", default=2400.0, gt=0,
    )
    plate_length_mm: float = _field(
        label="Plate length", symbol="Lp", unit="mm",
        help_text="Length of one shell plate around the circumference.",
        clause="5.6 shell design", default=6000.0, gt=0,
    )
    include_roof_calculation: bool = _field(
        label="Include roof calculation", symbol="roof_on", unit="",
        help_text="Untick to skip the roof sizing and report the shell/openings only.",
        clause="5.10 roof design", default=True,
    )
    roof_type: Literal["cone", "dome", "floating"] = _field(
        label="Roof type", symbol="roof", unit="",
        help_text="Fixed cone/dome roof or floating deck.",
        clause="5.10 roof design", default="cone",
    )
    roof_slope_ratio: float = _field(
        label="Cone roof slope", symbol="s", unit="",
        help_text="Cone roof rise per unit run (a 1:6 slope is 0.1667).",
        clause="5.10 roof design", default=0.1667, gt=0,
    )
    roof_rise_mm: float = _field(
        label="Dome roof rise", symbol="h", unit="mm",
        help_text="Vertical rise of a dome roof above the shell top (dome roofs only).",
        clause="5.10 roof design", default=500.0, gt=0,
    )
    roof_live_load_kpa: float = _field(
        label="Roof live load", symbol="q_L", unit="kPa",
        help_text="Design roof live load per unit area (confirm the applicable minimum).",
        clause="5.10 roof design", default=1.2, ge=0.0,
    )
    roof_dead_load_kpa: float = _field(
        label="Roof dead load", symbol="q_D", unit="kPa",
        help_text="Roof self-weight and attached items per unit area.",
        clause="5.10 roof design", default=0.5, ge=0.0,
    )
    opening_outside_diameter_mm: float | None = _field(
        label="Opening outside diameter", symbol="d_o", unit="mm",
        help_text="If given, a simplified shell-opening reinforcement check runs (TK-3).",
        clause="5.7 openings", default=None, gt=0,
    )
    opening_neck_thickness_mm: float | None = _field(
        label="Opening neck thickness", symbol="t_n", unit="mm",
        help_text="Provided nozzle-neck wall thickness for the opening check.",
        clause="5.7 openings", default=None, gt=0,
    )
    opening_projection_mm: float = _field(
        label="Opening projection", symbol="a", unit="mm",
        help_text="Outward projection used for the nozzle excess area credit.",
        clause="5.7 openings", default=150.0, gt=0,
    )
