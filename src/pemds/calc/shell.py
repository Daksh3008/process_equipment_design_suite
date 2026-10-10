"""Cylindrical shells under internal pressure — ASME VIII-1 UG-27(c).

Implements the circumferential and longitudinal stress equations and their
inversions for MAWP. All quantities are internal SI: pressure and stress in Pa,
length in m.
"""

from __future__ import annotations

from ..core.calc import CodeEditions, citation_for, provable
from ..core.result import Result
from ..core.standards import ASME_VIII_1
from ..core.units import format_value
from .common import make_result, require_positive


@provable(ASME_VIII_1, "UG-27(c)(1)", "S1")
def circumferential_thickness(
    pressure_pa: float,
    inside_radius_m: float,
    allowable_stress_pa: float,
    joint_efficiency: float,
    editions: CodeEditions,
    corrosion_allowance_m: float = 0.0,
) -> Result:
    """Required wall thickness for the circumferential joint (UG-27(c)(1))."""
    require_positive(P=pressure_pa, R=inside_radius_m, S=allowable_stress_pa, E=joint_efficiency)
    if corrosion_allowance_m < 0:
        raise ValueError(f"corrosion_allowance_m must be >= 0, got {corrosion_allowance_m}")
    denominator = allowable_stress_pa * joint_efficiency - 0.6 * pressure_pa
    if denominator <= 0:
        raise ValueError(
            "UG-27(c)(1) requires S*E > 0.6*P; "
            f"got S={allowable_stress_pa:g} Pa, E={joint_efficiency:g}, P={pressure_pa:g} Pa"
        )
    pressure_thickness = pressure_pa * inside_radius_m / denominator
    total = pressure_thickness + corrosion_allowance_m
    return make_result(
        symbol="t",
        value=total,
        kind="length",
        formula="t = P*R/(S*E - 0.6*P) + CA",
        substitutions={
            "P": format_value(pressure_pa, "Pa"),
            "R": format_value(inside_radius_m, "m"),
            "S": format_value(allowable_stress_pa, "Pa"),
            "E": f"{joint_efficiency:g}",
            "CA": format_value(corrosion_allowance_m, "m"),
        },
        citation=citation_for(circumferential_thickness, editions),
        inputs_used=[
            "pressure_pa",
            "inside_radius_m",
            "allowable_stress_pa",
            "joint_efficiency",
            "corrosion_allowance_m",
        ],
        children=[
            make_result(
                symbol="t_p",
                value=pressure_thickness,
                kind="length",
                formula="t_p = P*R/(S*E - 0.6*P)",
                substitutions={
                    "P": format_value(pressure_pa, "Pa"),
                    "R": format_value(inside_radius_m, "m"),
                    "S": format_value(allowable_stress_pa, "Pa"),
                    "E": f"{joint_efficiency:g}",
                },
                citation=citation_for(circumferential_thickness, editions),
            )
        ],
    )


@provable(ASME_VIII_1, "UG-27(c)(1)", "S1")
def circumferential_mawp(
    pressure_thickness_m: float,
    inside_radius_m: float,
    allowable_stress_pa: float,
    joint_efficiency: float,
    editions: CodeEditions,
) -> Result:
    """MAWP from the circumferential joint, net of corrosion allowance."""
    require_positive(
        t=pressure_thickness_m, R=inside_radius_m, S=allowable_stress_pa, E=joint_efficiency
    )
    mawp = (
        allowable_stress_pa
        * joint_efficiency
        * pressure_thickness_m
        / (inside_radius_m + 0.6 * pressure_thickness_m)
    )
    return make_result(
        symbol="P",
        value=mawp,
        kind="pressure",
        formula="P = S*E*t/(R + 0.6*t)",
        substitutions={
            "S": format_value(allowable_stress_pa, "Pa"),
            "E": f"{joint_efficiency:g}",
            "t": format_value(pressure_thickness_m, "m"),
            "R": format_value(inside_radius_m, "m"),
        },
        citation=citation_for(circumferential_mawp, editions),
        inputs_used=[
            "pressure_thickness_m",
            "inside_radius_m",
            "allowable_stress_pa",
            "joint_efficiency",
        ],
    )


@provable(ASME_VIII_1, "UG-27(c)(2)", "S1")
def longitudinal_thickness(
    pressure_pa: float,
    inside_radius_m: float,
    allowable_stress_pa: float,
    joint_efficiency: float,
    editions: CodeEditions,
    corrosion_allowance_m: float = 0.0,
) -> Result:
    """Required wall thickness for the longitudinal joint (UG-27(c)(2))."""
    require_positive(P=pressure_pa, R=inside_radius_m, S=allowable_stress_pa, E=joint_efficiency)
    if corrosion_allowance_m < 0:
        raise ValueError(f"corrosion_allowance_m must be >= 0, got {corrosion_allowance_m}")
    pressure_thickness = pressure_pa * inside_radius_m / (
        2.0 * allowable_stress_pa * joint_efficiency + 0.4 * pressure_pa
    )
    total = pressure_thickness + corrosion_allowance_m
    return make_result(
        symbol="t",
        value=total,
        kind="length",
        formula="t = P*R/(2*S*E + 0.4*P) + CA",
        substitutions={
            "P": format_value(pressure_pa, "Pa"),
            "R": format_value(inside_radius_m, "m"),
            "S": format_value(allowable_stress_pa, "Pa"),
            "E": f"{joint_efficiency:g}",
            "CA": format_value(corrosion_allowance_m, "m"),
        },
        citation=citation_for(longitudinal_thickness, editions),
        inputs_used=[
            "pressure_pa",
            "inside_radius_m",
            "allowable_stress_pa",
            "joint_efficiency",
            "corrosion_allowance_m",
        ],
    )


@provable(ASME_VIII_1, "UG-27(c)(2)", "S1")
def longitudinal_mawp(
    pressure_thickness_m: float,
    inside_radius_m: float,
    allowable_stress_pa: float,
    joint_efficiency: float,
    editions: CodeEditions,
) -> Result:
    """MAWP from the longitudinal joint, net of corrosion allowance."""
    require_positive(
        t=pressure_thickness_m, R=inside_radius_m, S=allowable_stress_pa, E=joint_efficiency
    )
    denominator = inside_radius_m - 0.4 * pressure_thickness_m
    if denominator <= 0:
        raise ValueError(
            f"UG-27(c)(2) inversion requires R > 0.4*t; got R={inside_radius_m:g} m, "
            f"t={pressure_thickness_m:g} m"
        )
    mawp = 2.0 * allowable_stress_pa * joint_efficiency * pressure_thickness_m / denominator
    return make_result(
        symbol="P",
        value=mawp,
        kind="pressure",
        formula="P = 2*S*E*t/(R - 0.4*t)",
        substitutions={
            "S": format_value(allowable_stress_pa, "Pa"),
            "E": f"{joint_efficiency:g}",
            "t": format_value(pressure_thickness_m, "m"),
            "R": format_value(inside_radius_m, "m"),
        },
        citation=citation_for(longitudinal_mawp, editions),
        inputs_used=[
            "pressure_thickness_m",
            "inside_radius_m",
            "allowable_stress_pa",
            "joint_efficiency",
        ],
    )
