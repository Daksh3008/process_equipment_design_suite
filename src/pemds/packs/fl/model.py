"""Input model for the flange/nozzle pack (IN-1, FR-FL).

Fields are user-facing (NPS labels, MPa, degC) and converted to internal SI at
the pack boundary. Every field carries label, symbol, unit, help text and the
clause it feeds, so GUI-1/2/4 and RP-2 fall out automatically.
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


class ConnectionInput(BaseModel):
    """One flanged connection in the nozzle-size schedule (FL-3)."""

    model_config = ConfigDict(extra="forbid")

    tag: str = _field(
        label="Connection tag",
        symbol="N",
        unit="",
        help_text="Identifier shown on the nozzle schedule and report.",
        clause="n/a",
        default="N1",
    )
    size: str = _field(
        label="Nominal size (NPS)",
        symbol="DN",
        unit="",
        help_text="B16.5 nominal pipe size, e.g. '2' or '1/2'.",
        clause="Section 3, size",
    )
    service: str = _field(
        label="Service",
        symbol="svc",
        unit="",
        help_text="Short service description shown on the schedule.",
        clause="n/a",
        default="",
    )
    minimum_class: int | None = _field(
        label="Minimum class",
        symbol="class_min",
        unit="",
        help_text="Optional floor for the selected pressure class (e.g. 300).",
        clause="Section 2, pressure-temperature ratings",
        default=None,
    )


class FlangeInputs(BaseModel):
    """Inputs to query a flange rating, bolt-up and connection schedule (FR-FL)."""

    model_config = ConfigDict(extra="forbid")

    tag: str = _field(
        label="Equipment tag",
        symbol="tag",
        unit="",
        help_text="Identifier used on the report and schedule.",
        clause="n/a",
        default="FL-101",
    )
    size: str = _field(
        label="Nominal size (NPS)",
        symbol="DN",
        unit="",
        help_text="B16.5 nominal pipe size for the primary rating query, e.g. '2'.",
        clause="Section 3, size",
    )
    material_group: str = _field(
        label="Material group",
        symbol="group",
        unit="",
        help_text="B16.5 material group identifier (e.g. '1.1' carbon steel, '2.2' austenitic).",
        clause="Section 2, pressure-temperature ratings",
        default="1.1",
    )
    design_pressure_mpa: float = _field(
        label="Design pressure",
        symbol="P",
        unit="MPa",
        help_text="Internal design gauge pressure used for the rating query.",
        clause="Section 2, pressure-temperature ratings",
        gt=0.0,
    )
    design_temperature_c: float = _field(
        label="Design temperature",
        symbol="T",
        unit="degC",
        help_text="Design temperature used to look up the rating step.",
        clause="Section 2, pressure-temperature ratings",
    )
    minimum_class: int | None = _field(
        label="Minimum class",
        symbol="class_min",
        unit="",
        help_text="Optional floor for the selected pressure class; the lowest qualifying class is used.",
        clause="Section 2, pressure-temperature ratings",
        default=None,
    )
    gasket_type: Literal["spiral-wound", "sheet", "ring-joint"] = _field(
        label="Gasket type",
        symbol="gasket",
        unit="",
        help_text="Gasket type key from the B16.20 gasket table.",
        clause="Gasket m and y factors",
        default="spiral-wound",
    )
    facing: Literal["raised_face", "flat_face", "ring_joint"] = _field(
        label="Facing",
        symbol="facing",
        unit="",
        help_text="Flange facing: raised face, flat face or ring joint.",
        clause="Flange facing and mating dimensions",
        default="raised_face",
    )
    gasket_mean_diameter_mm: float = _field(
        label="Gasket mean diameter",
        symbol="G",
        unit="mm",
        help_text="Mean gasket diameter used by the bolt-load form.",
        clause="Bolting dimensions and materials",
        default=100.0,
        gt=0.0,
    )
    gasket_contact_width_mm: float | None = _field(
        label="Gasket contact width",
        symbol="N",
        unit="mm",
        help_text="Gasket contact width; if omitted the value for the chosen type is used.",
        clause="Gasket m and y factors",
        default=None,
        gt=0.0,
    )
    bolt_allowable_stress_mpa: float = _field(
        label="Bolt allowable stress",
        symbol="Sb",
        unit="MPa",
        help_text="Allowable bolt stress at design temperature (user-supplied pending bolt material data).",
        clause="Bolting dimensions and materials",
        default=138.0,
        gt=0.0,
    )
    nut_factor_k: float = _field(
        label="Nut factor",
        symbol="K",
        unit="",
        help_text="Dimensionless torque-preload nut factor (0.2 typical for as-received steel).",
        clause="Bolting dimensions and materials",
        default=0.2,
        gt=0.0,
        le=1.0,
    )
    connections: list[ConnectionInput] = Field(
        default_factory=list,
        json_schema_extra={
            "label": "Nozzle schedule",
            "symbol": "connections",
            "unit": "",
            "help": "Connections whose per-size class selection and mating pair are reported (FL-3).",
            "clause": "Section 2, pressure-temperature ratings",
        },
    )
