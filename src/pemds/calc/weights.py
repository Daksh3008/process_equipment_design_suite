"""Weight and centre of gravity — PV-4 (UG-22 loads).

Metal and liquid masses are computed from the vessel geometry and the material
density. Head metal volumes use published closed-form surface-area factors for
each head type; the centre of gravity of a vertical vessel lies on the axis of
rotation and is reported at mid-height as an engineering estimate.
"""

from __future__ import annotations

import math

from ..core.calc import CodeEditions, citation_for, provable
from ..core.geometry import HEAD_DEPTH_FACTOR
from ..core.result import Result
from ..core.standards import ASME_VIII_1
from ..core.units import format_value
from .common import make_result, require_positive

#: Approximate outer surface-area factors for head shapes (times pi * R^2).
_HEAD_SURFACE_FACTOR = {
    "ellipsoidal": 1.084,  # 2:1 ellipsoid
    "torispherical": 0.984,
    "hemispherical": 2.0,
    "flat": 1.0,
}

#: Internal volume factors for ONE head (times pi * R_i^3).
_HEAD_VOLUME_FACTOR = {
    "ellipsoidal": 0.3333333333333333,  # (1/3) * R^3 for a 2:1 ellipsoidal half
    "torispherical": 0.309,
    "hemispherical": 0.6666666666666666,  # (2/3) * R^3
    "flat": 0.0,
}


@provable(ASME_VIII_1, "UG-22", "S1")
def vessel_metal_mass(
    inside_diameter_m: float,
    shell_length_m: float,
    shell_metal_thickness_m: float,
    head_metal_thickness_m: float,
    head_type: str,
    density_kg_m3: float,
    editions: CodeEditions,
) -> Result:
    """Empty weight of the shell and two heads (PV-4, UG-22)."""
    require_positive(
        D=inside_diameter_m,
        L=shell_length_m,
        t_s=shell_metal_thickness_m,
        t_h=head_metal_thickness_m,
        rho=density_kg_m3,
    )
    radius_outer = inside_diameter_m / 2.0 + shell_metal_thickness_m
    shell_volume = math.pi * (radius_outer**2 - (inside_diameter_m / 2.0) ** 2) * shell_length_m
    head_surface = _HEAD_SURFACE_FACTOR.get(head_type)
    if head_surface is None:
        raise ValueError(f"no surface factor for head type {head_type!r}")
    head_volume = head_surface * math.pi * radius_outer**2 * head_metal_thickness_m
    metal_volume = shell_volume + 2.0 * head_volume
    mass = density_kg_m3 * metal_volume
    return make_result(
        symbol="W_empty",
        value=mass,
        kind="mass",
        formula="W = rho * (pi*(Ro^2 - Ri^2)*L + 2*S_head*t_h)",
        substitutions={
            "D (inside)": format_value(inside_diameter_m, "m"),
            "L": format_value(shell_length_m, "m"),
            "t_s (metal)": format_value(shell_metal_thickness_m, "m"),
            "t_h (metal)": format_value(head_metal_thickness_m, "m"),
            "head": head_type,
            "rho": format_value(density_kg_m3, "kg/m**3"),
        },
        citation=citation_for(vessel_metal_mass, editions),
        inputs_used=["inside_diameter_m", "shell_length_m", "shell_metal_thickness_m", "density_kg_m3"],
    )


@provable(ASME_VIII_1, "UG-22", "S1")
def liquid_fill_mass(
    inside_diameter_m: float,
    shell_length_m: float,
    head_type: str,
    liquid_density_kg_m3: float,
    editions: CodeEditions,
) -> Result:
    """Mass of liquid required to fill the shell and two heads."""

    require_positive(
        D=inside_diameter_m, L=shell_length_m, rho=liquid_density_kg_m3
    )
    radius_inner = inside_diameter_m / 2.0
    factor = _HEAD_VOLUME_FACTOR.get(head_type)
    if factor is None:
        raise ValueError(f"no volume factor for head type {head_type!r}")
    shell_volume = math.pi * radius_inner**2 * shell_length_m
    head_volume = factor * math.pi * radius_inner**3
    total_volume = shell_volume + 2.0 * head_volume
    mass = liquid_density_kg_m3 * total_volume
    return make_result(
        symbol="W_liquid",
        value=mass,
        kind="mass",
        formula="W_liq = rho_liq * (pi*Ri^2*L + 2*V_head)",
        substitutions={
            "D (inside)": format_value(inside_diameter_m, "m"),
            "L": format_value(shell_length_m, "m"),
            "head": head_type,
            "rho_liq": format_value(liquid_density_kg_m3, "kg/m**3"),
        },
        citation=citation_for(liquid_fill_mass, editions),
        inputs_used=["inside_diameter_m", "shell_length_m", "head_type", "liquid_density_kg_m3"],
    )


@provable(ASME_VIII_1, "UG-22", "S1")
def operating_weight(
    empty_mass_kg: float,
    fill_liquid_mass_kg: float,
    editions: CodeEditions,
) -> Result:
    """Operating weight = empty metal + contained liquid."""

    require_positive(empty=empty_mass_kg)
    if fill_liquid_mass_kg < 0:
        raise ValueError(f"fill mass must be >= 0, got {fill_liquid_mass_kg}")
    total = empty_mass_kg + fill_liquid_mass_kg
    return make_result(
        symbol="W_operating",
        value=total,
        kind="mass",
        formula="W_operating = W_empty + W_liquid",
        substitutions={
            "W_empty": format_value(empty_mass_kg, "kg"),
            "W_liquid": format_value(fill_liquid_mass_kg, "kg"),
        },
        citation=citation_for(operating_weight, editions),
        inputs_used=["empty_mass_kg", "fill_liquid_mass_kg"],
    )


def head_depth_m(head_type: str, inside_diameter_m: float) -> float:
    """Head depth from the shared factor table (CoG estimate)."""
    require_positive(D=inside_diameter_m)
    try:
        factor = HEAD_DEPTH_FACTOR[head_type]
    except KeyError as exc:
        raise ValueError(f"no depth factor for head type {head_type!r}") from exc
    return factor * inside_diameter_m


@provable(ASME_VIII_1, "UG-22", "S1")
def centre_of_gravity_height(
    shell_length_m: float,
    head_depth_m: float,
    editions: CodeEditions,
) -> Result:
    """CoG height above the bottom tangent for a vertical vessel (on-axis)."""

    require_positive(L=shell_length_m)
    if head_depth_m < 0:
        raise ValueError(f"head_depth_m must be >= 0, got {head_depth_m}")
    height = (shell_length_m + 2.0 * head_depth_m) / 2.0
    return make_result(
        symbol="z_cg",
        value=height,
        kind="length",
        formula="z_cg = (L + 2*h_head)/2 (vertical vessel, on-axis)",
        substitutions={
            "L": format_value(shell_length_m, "m"),
            "h_head": format_value(head_depth_m, "m"),
        },
        citation=citation_for(centre_of_gravity_height, editions),
        inputs_used=["shell_length_m", "head_depth_m"],
    )