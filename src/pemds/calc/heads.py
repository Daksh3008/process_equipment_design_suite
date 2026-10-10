"""Formed heads under internal pressure — ASME VIII-1 UG-32.

Ellipsoidal, torispherical, hemispherical and conical heads. All quantities are
internal SI: pressure and stress in Pa, length in m.
"""

from __future__ import annotations

import math

from ..core.calc import CodeEditions, citation_for, provable
from ..core.result import Result
from ..core.standards import ASME_VIII_1
from ..core.units import format_value
from .common import make_result, require_positive


def _head_result(
    *,
    symbol: str,
    pressure_thickness: float,
    corrosion_allowance_m: float,
    formula: str,
    substitutions: dict[str, str],
    citation,
    inputs_used: list[str],
) -> Result:
    if corrosion_allowance_m < 0:
        raise ValueError(f"corrosion_allowance_m must be >= 0, got {corrosion_allowance_m}")
    return make_result(
        symbol=symbol,
        value=pressure_thickness + corrosion_allowance_m,
        kind="length",
        formula=formula,
        substitutions=substitutions,
        citation=citation,
        inputs_used=inputs_used,
    )


@provable(ASME_VIII_1, "UG-32(c)", "S1")
def ellipsoidal_thickness(
    pressure_pa: float,
    inside_diameter_m: float,
    allowable_stress_pa: float,
    joint_efficiency: float,
    editions: CodeEditions,
    corrosion_allowance_m: float = 0.0,
) -> Result:
    """Required thickness of a 2:1 ellipsoidal head (UG-32(c))."""
    require_positive(P=pressure_pa, D=inside_diameter_m, S=allowable_stress_pa, E=joint_efficiency)
    denominator = 2.0 * allowable_stress_pa * joint_efficiency - 0.2 * pressure_pa
    if denominator <= 0:
        raise ValueError(
            f"UG-32(c) requires 2*S*E > 0.2*P; got S={allowable_stress_pa:g} Pa, "
            f"E={joint_efficiency:g}, P={pressure_pa:g} Pa"
        )
    return _head_result(
        symbol="t",
        pressure_thickness=pressure_pa * inside_diameter_m / denominator,
        corrosion_allowance_m=corrosion_allowance_m,
        formula="t = P*D/(2*S*E - 0.2*P) + CA",
        substitutions={
            "P": format_value(pressure_pa, "Pa"),
            "D": format_value(inside_diameter_m, "m"),
            "S": format_value(allowable_stress_pa, "Pa"),
            "E": f"{joint_efficiency:g}",
            "CA": format_value(corrosion_allowance_m, "m"),
        },
        citation=citation_for(ellipsoidal_thickness, editions),
        inputs_used=["pressure_pa", "inside_diameter_m", "allowable_stress_pa", "joint_efficiency"],
    )


@provable(ASME_VIII_1, "UG-32(d)", "S1")
def torispherical_thickness(
    pressure_pa: float,
    crown_radius_m: float,
    allowable_stress_pa: float,
    joint_efficiency: float,
    editions: CodeEditions,
    corrosion_allowance_m: float = 0.0,
) -> Result:
    """Required thickness of a torispherical head (UG-32(d))."""
    require_positive(P=pressure_pa, L=crown_radius_m, S=allowable_stress_pa, E=joint_efficiency)
    denominator = allowable_stress_pa * joint_efficiency - 0.1 * pressure_pa
    if denominator <= 0:
        raise ValueError(
            f"UG-32(d) requires S*E > 0.1*P; got S={allowable_stress_pa:g} Pa, "
            f"E={joint_efficiency:g}, P={pressure_pa:g} Pa"
        )
    return _head_result(
        symbol="t",
        pressure_thickness=0.885 * pressure_pa * crown_radius_m / denominator,
        corrosion_allowance_m=corrosion_allowance_m,
        formula="t = 0.885*P*L/(S*E - 0.1*P) + CA",
        substitutions={
            "P": format_value(pressure_pa, "Pa"),
            "L": format_value(crown_radius_m, "m"),
            "S": format_value(allowable_stress_pa, "Pa"),
            "E": f"{joint_efficiency:g}",
            "CA": format_value(corrosion_allowance_m, "m"),
        },
        citation=citation_for(torispherical_thickness, editions),
        inputs_used=["pressure_pa", "crown_radius_m", "allowable_stress_pa", "joint_efficiency"],
    )


@provable(ASME_VIII_1, "UG-32(e)", "S1")
def hemispherical_thickness(
    pressure_pa: float,
    inside_radius_m: float,
    allowable_stress_pa: float,
    joint_efficiency: float,
    editions: CodeEditions,
    corrosion_allowance_m: float = 0.0,
) -> Result:
    """Required thickness of a hemispherical head (UG-32(e))."""
    require_positive(P=pressure_pa, L=inside_radius_m, S=allowable_stress_pa, E=joint_efficiency)
    denominator = 2.0 * allowable_stress_pa * joint_efficiency - 0.2 * pressure_pa
    if denominator <= 0:
        raise ValueError(
            f"UG-32(e) requires 2*S*E > 0.2*P; got S={allowable_stress_pa:g} Pa, "
            f"E={joint_efficiency:g}, P={pressure_pa:g} Pa"
        )
    return _head_result(
        symbol="t",
        pressure_thickness=pressure_pa * inside_radius_m / denominator,
        corrosion_allowance_m=corrosion_allowance_m,
        formula="t = P*L/(2*S*E - 0.2*P) + CA",
        substitutions={
            "P": format_value(pressure_pa, "Pa"),
            "L": format_value(inside_radius_m, "m"),
            "S": format_value(allowable_stress_pa, "Pa"),
            "E": f"{joint_efficiency:g}",
            "CA": format_value(corrosion_allowance_m, "m"),
        },
        citation=citation_for(hemispherical_thickness, editions),
        inputs_used=["pressure_pa", "inside_radius_m", "allowable_stress_pa", "joint_efficiency"],
    )


@provable(ASME_VIII_1, "UG-32(f)", "S1")
def conical_thickness(
    pressure_pa: float,
    inside_diameter_m: float,
    half_apex_angle_deg: float,
    allowable_stress_pa: float,
    joint_efficiency: float,
    editions: CodeEditions,
    corrosion_allowance_m: float = 0.0,
) -> Result:
    """Required thickness of a conical shell, half-apex angle <= 30 deg (UG-32(f))."""
    require_positive(P=pressure_pa, D=inside_diameter_m, S=allowable_stress_pa, E=joint_efficiency)
    if not 0.0 < half_apex_angle_deg <= 30.0:
        raise ValueError(
            f"UG-32(f) conical rule applies for half-apex angle 0 < a <= 30 deg, got {half_apex_angle_deg}"
        )
    cos_alpha = math.cos(math.radians(half_apex_angle_deg))
    denominator = 2.0 * cos_alpha * (allowable_stress_pa * joint_efficiency - 0.6 * pressure_pa)
    if denominator <= 0:
        raise ValueError(
            f"UG-32(f) requires S*E > 0.6*P; got S={allowable_stress_pa:g} Pa, "
            f"E={joint_efficiency:g}, P={pressure_pa:g} Pa"
        )
    return _head_result(
        symbol="t",
        pressure_thickness=pressure_pa * inside_diameter_m / denominator,
        corrosion_allowance_m=corrosion_allowance_m,
        formula="t = P*D/(2*cos(a)*(S*E - 0.6*P)) + CA",
        substitutions={
            "P": format_value(pressure_pa, "Pa"),
            "D": format_value(inside_diameter_m, "m"),
            "a": f"{half_apex_angle_deg:g} deg",
            "S": format_value(allowable_stress_pa, "Pa"),
            "E": f"{joint_efficiency:g}",
            "CA": format_value(corrosion_allowance_m, "m"),
        },
        citation=citation_for(conical_thickness, editions),
        inputs_used=[
            "pressure_pa",
            "inside_diameter_m",
            "half_apex_angle_deg",
            "allowable_stress_pa",
            "joint_efficiency",
        ],
    )


@provable(ASME_VIII_1, "UG-32(c)", "S1")
def ellipsoidal_mawp(
    pressure_thickness_m: float,
    inside_diameter_m: float,
    allowable_stress_pa: float,
    joint_efficiency: float,
    editions: CodeEditions,
) -> Result:
    """MAWP of a 2:1 ellipsoidal head from its pressure thickness."""
    require_positive(t=pressure_thickness_m, D=inside_diameter_m, S=allowable_stress_pa, E=joint_efficiency)
    mawp = (
        2.0
        * allowable_stress_pa
        * joint_efficiency
        * pressure_thickness_m
        / (inside_diameter_m + 0.2 * pressure_thickness_m)
    )
    return make_result(
        symbol="P",
        value=mawp,
        kind="pressure",
        formula="P = 2*S*E*t/(D + 0.2*t)",
        substitutions={
            "S": format_value(allowable_stress_pa, "Pa"),
            "E": f"{joint_efficiency:g}",
            "t": format_value(pressure_thickness_m, "m"),
            "D": format_value(inside_diameter_m, "m"),
        },
        citation=citation_for(ellipsoidal_mawp, editions),
        inputs_used=["pressure_thickness_m", "inside_diameter_m", "allowable_stress_pa", "joint_efficiency"],
    )


@provable(ASME_VIII_1, "UG-32(d)", "S1")
def torispherical_mawp(
    pressure_thickness_m: float,
    crown_radius_m: float,
    allowable_stress_pa: float,
    joint_efficiency: float,
    editions: CodeEditions,
) -> Result:
    """MAWP of a torispherical head from its pressure thickness."""
    require_positive(t=pressure_thickness_m, L=crown_radius_m, S=allowable_stress_pa, E=joint_efficiency)
    mawp = (
        allowable_stress_pa
        * joint_efficiency
        * pressure_thickness_m
        / (0.885 * crown_radius_m + 0.1 * pressure_thickness_m)
    )
    return make_result(
        symbol="P",
        value=mawp,
        kind="pressure",
        formula="P = S*E*t/(0.885*L + 0.1*t)",
        substitutions={
            "S": format_value(allowable_stress_pa, "Pa"),
            "E": f"{joint_efficiency:g}",
            "t": format_value(pressure_thickness_m, "m"),
            "L": format_value(crown_radius_m, "m"),
        },
        citation=citation_for(torispherical_mawp, editions),
        inputs_used=["pressure_thickness_m", "crown_radius_m", "allowable_stress_pa", "joint_efficiency"],
    )


@provable(ASME_VIII_1, "UG-32(e)", "S1")
def hemispherical_mawp(
    pressure_thickness_m: float,
    inside_radius_m: float,
    allowable_stress_pa: float,
    joint_efficiency: float,
    editions: CodeEditions,
) -> Result:
    """MAWP of a hemispherical head from its pressure thickness."""
    require_positive(t=pressure_thickness_m, L=inside_radius_m, S=allowable_stress_pa, E=joint_efficiency)
    mawp = (
        2.0
        * allowable_stress_pa
        * joint_efficiency
        * pressure_thickness_m
        / (inside_radius_m + 0.2 * pressure_thickness_m)
    )
    return make_result(
        symbol="P",
        value=mawp,
        kind="pressure",
        formula="P = 2*S*E*t/(L + 0.2*t)",
        substitutions={
            "S": format_value(allowable_stress_pa, "Pa"),
            "E": f"{joint_efficiency:g}",
            "t": format_value(pressure_thickness_m, "m"),
            "L": format_value(inside_radius_m, "m"),
        },
        citation=citation_for(hemispherical_mawp, editions),
        inputs_used=["pressure_thickness_m", "inside_radius_m", "allowable_stress_pa", "joint_efficiency"],
    )
