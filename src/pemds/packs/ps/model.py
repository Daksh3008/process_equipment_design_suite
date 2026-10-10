"""Input model for the piping pack (IN-1)."""

from __future__ import annotations

from typing import Any

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


class PipeInputs(BaseModel):
    """Inputs to size a straight run of piping (B31.3, FR-PS)."""

    model_config = ConfigDict(extra="forbid")

    tag: str = _field(
        label="Tag", symbol="tag", unit="", help_text="Line/equipment identifier.",
        clause="n/a", default="L-101",
    )
    outside_diameter_mm: float = _field(
        label="Outside diameter", symbol="D", unit="mm",
        help_text="Nominal outside diameter of the pipe (304.1.2).",
        clause="304.1.2", gt=0,
    )
    design_pressure_mpa: float = _field(
        label="Design pressure", symbol="P", unit="MPa",
        help_text="Internal design gauge pressure (302.2.4).", clause="302.2.4", gt=0,
    )
    design_temperature_c: float = _field(
        label="Design temperature", symbol="T", unit="degC",
        help_text="Design metal temperature used for allowable stress.",
        clause="301.3",
    )
    material_key: str = _field(
        label="Pipe material", symbol="mat", unit="",
        help_text="Material key from the materials database.", clause="ASME II-D",
    )
    corrosion_allowance_mm: float = _field(
        label="Corrosion allowance", symbol="CA", unit="mm",
        help_text="Wall added for corrosion/erosion (304.1.2).", clause="304.1.2",
        default=0.0, ge=0,
    )
    weld_joint_factor: float = _field(
        label="Weld joint factor", symbol="E", unit="",
        help_text="Longitudinal weld joint factor E (seamless = 1.0) (302.3.4).",
        clause="302.3.4", default=1.0, gt=0.0, le=1.0,
    )
    y_factor: float = _field(
        label="Y factor", symbol="Y", unit="",
        help_text="Coefficient from 304.1.1 (0.4 for ferritic steels up to 482 degC).",
        clause="304.1.1", default=0.4, ge=0.0, le=1.0,
    )
    mill_tolerance_pct: float = _field(
        label="Mill tolerance", symbol="tol", unit="%",
        help_text="Under-thickness percent of the wall (typ. 12.5%).",
        clause="304.1.2", default=0.0, ge=0.0, le=99.0,
    )
    provided_wall_thickness_mm: float | None = _field(
        label="Provided wall thickness", symbol="t", unit="mm",
        help_text="Supplied wall; if given, a pass/fail check is reported.",
        clause="304.1.2", default=None, gt=0,
    )
    branch_outside_diameter_mm: float | None = _field(
        label="Branch outside diameter", symbol="d_b", unit="mm",
        help_text="If given, a simplified branch reinforcement check runs (EXPERIMENTAL).",
        clause="304.3", default=None, gt=0,
    )