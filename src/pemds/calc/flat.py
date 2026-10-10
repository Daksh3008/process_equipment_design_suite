"""Flat heads, covers and blind flanges — ASME VIII-1 UG-34.

``t = d * sqrt(C * P / (S * E)) + CA``. The factor ``C`` depends on the head
configuration and attachment and is supplied by the caller from UG-34's table.
"""

from __future__ import annotations

import math

from ..core.calc import CodeEditions, citation_for, provable
from ..core.result import Result
from ..core.standards import ASME_VIII_1
from ..core.units import format_value
from .common import make_result, require_positive


@provable(ASME_VIII_1, "UG-34(c)(2)", "S1")
def flat_head_thickness(
    pressure_pa: float,
    inside_diameter_m: float,
    factor_c: float,
    allowable_stress_pa: float,
    joint_efficiency: float,
    editions: CodeEditions,
    corrosion_allowance_m: float = 0.0,
) -> Result:
    """Required thickness of an unstayed flat head or cover (UG-34(c)(2)).

    ``factor_c`` is the configuration factor from the UG-34 table (dimensionless,
    typically 0.13 to 0.33).
    """
    require_positive(P=pressure_pa, d=inside_diameter_m, C=factor_c, S=allowable_stress_pa, E=joint_efficiency)
    if corrosion_allowance_m < 0:
        raise ValueError(f"corrosion_allowance_m must be >= 0, got {corrosion_allowance_m}")
    pressure_thickness = inside_diameter_m * math.sqrt(
        factor_c * pressure_pa / (allowable_stress_pa * joint_efficiency)
    )
    total = pressure_thickness + corrosion_allowance_m
    return make_result(
        symbol="t",
        value=total,
        kind="length",
        formula="t = d*sqrt(C*P/(S*E)) + CA",
        substitutions={
            "d": format_value(inside_diameter_m, "m"),
            "C": f"{factor_c:g}",
            "P": format_value(pressure_pa, "Pa"),
            "S": format_value(allowable_stress_pa, "Pa"),
            "E": f"{joint_efficiency:g}",
            "CA": format_value(corrosion_allowance_m, "m"),
        },
        citation=citation_for(flat_head_thickness, editions),
        inputs_used=[
            "pressure_pa",
            "inside_diameter_m",
            "factor_c",
            "allowable_stress_pa",
            "joint_efficiency",
        ],
    )


@provable(ASME_VIII_1, "UG-34(c)(2)", "S1")
def flat_head_mawp(
    pressure_thickness_m: float,
    inside_diameter_m: float,
    factor_c: float,
    allowable_stress_pa: float,
    joint_efficiency: float,
    editions: CodeEditions,
) -> Result:
    """MAWP of a flat head from its pressure thickness (UG-34(c)(2))."""
    require_positive(
        t=pressure_thickness_m,
        d=inside_diameter_m,
        C=factor_c,
        S=allowable_stress_pa,
        E=joint_efficiency,
    )
    mawp = (
        allowable_stress_pa * joint_efficiency / factor_c * (pressure_thickness_m / inside_diameter_m) ** 2
    )
    return make_result(
        symbol="P",
        value=mawp,
        kind="pressure",
        formula="P = (S*E/C)*(t/d)^2",
        substitutions={
            "S": format_value(allowable_stress_pa, "Pa"),
            "E": f"{joint_efficiency:g}",
            "C": f"{factor_c:g}",
            "t": format_value(pressure_thickness_m, "m"),
            "d": format_value(inside_diameter_m, "m"),
        },
        citation=citation_for(flat_head_mawp, editions),
        inputs_used=[
            "pressure_thickness_m",
            "inside_diameter_m",
            "factor_c",
            "allowable_stress_pa",
            "joint_efficiency",
        ],
    )
