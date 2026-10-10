"""Columns and reactors — tall-shell, skirt and wind/seismic checks (FR-CO).

STATUS: EXPERIMENTAL (VAL-2). The checks are transparent subsets:

* CO-1 combines the VIII-1 longitudinal pressure stress with the bending stress
  from an overturning moment at the skirt transition;
* CO-2 sizes the anchor bolts from the overturning tension and a cantilever base
  plate (ACI 318 anchorage / bearing forms);
* CO-3 builds the wind base moment from the ASCE 7 velocity pressure
  ``qz = 0.613*Kz*Kzt*Kd*V^2`` (Pa, V in m/s) and the seismic base shear
  ``V = Cs*W``.

All quantities are internal SI: length in m, pressure and stress in Pa, force in
N, moment in N*m.
"""

from __future__ import annotations

import math

from ..core.calc import CodeEditions, citation_for, provable
from ..core.provenance import VerificationStatus
from ..core.result import Issue, Result, Severity, Verdict
from ..core.standards import ACI_318, ASCE_7, ASME_VIII_1
from ..core.units import format_value
from .common import make_result, margin_verdict, require_positive

_EXPERIMENTAL = VerificationStatus.EXPERIMENTAL


def _experimental_warning(citation, detail: str) -> Issue:
    """The disclosure every experimental column/reactor result carries (VAL-2)."""
    return Issue(
        severity=Severity.WARNING,
        message=f"Column/reactor calculation is EXPERIMENTAL in v1.5: {detail}",
        rationale=(
            "CO checks are not validated against worked examples in v1.5; verify "
            "against the licensed editions before use."
        ),
        citation=citation,
    )


@provable(ASME_VIII_1, "UG-23 combined stress", "S1", verification=_EXPERIMENTAL)
def combined_longitudinal_stress(
    pressure_pa: float,
    inside_radius_m: float,
    metal_thickness_m: float,
    overturning_moment_nm: float,
    allowable_stress_pa: float,
    joint_efficiency: float,
    editions: CodeEditions,
) -> Result:
    """Combined longitudinal stress at the skirt transition (CO-1). EXPERIMENTAL.

    ``sigma = P*R/(2*t) + M/Z`` with the thin-wall section modulus
    ``Z = pi*(Do^4 - Di^4)/(32*Do)`` and ``Do = 2*R + 2*t``. The pressure and
    bending terms are added (conservative); the allowable is ``S*E``.
    """
    require_positive(
        P=pressure_pa,
        R=inside_radius_m,
        t=metal_thickness_m,
        S=allowable_stress_pa,
        E=joint_efficiency,
    )
    if overturning_moment_nm < 0:
        raise ValueError(f"overturning_moment_nm must be >= 0, got {overturning_moment_nm}")
    pressure_stress = pressure_pa * inside_radius_m / (2.0 * metal_thickness_m)
    inside_diameter = 2.0 * inside_radius_m
    outside_diameter = inside_diameter + 2.0 * metal_thickness_m
    section_modulus = (
        math.pi * (outside_diameter**4 - inside_diameter**4) / (32.0 * outside_diameter)
    )
    bending_stress = overturning_moment_nm / section_modulus
    total = pressure_stress + bending_stress
    allowable = allowable_stress_pa * joint_efficiency
    verdict, margin = margin_verdict(allowable, total)
    citation = citation_for(combined_longitudinal_stress, editions)
    return make_result(
        symbol="sigma_total",
        value=total,
        kind="stress",
        formula="sigma = P*R/(2*t) + M/Z;  Z = pi*(Do^4 - Di^4)/(32*Do)",
        substitutions={
            "P": format_value(pressure_pa, "Pa"),
            "R": format_value(inside_radius_m, "m"),
            "t (metal)": format_value(metal_thickness_m, "m"),
            "M": format_value(overturning_moment_nm, "N*m"),
            "sigma_p (pressure)": format_value(pressure_stress, "Pa"),
            "sigma_b (bending)": format_value(bending_stress, "Pa"),
            "allowable S*E": format_value(allowable, "Pa"),
        },
        citation=citation,
        inputs_used=[
            "design_pressure_mpa",
            "inside_diameter_mm",
            "provided_shell_thickness_mm",
            "overall_height_mm",
            "wind_speed_m_s",
            "seismic_cs",
        ],
        verdict=verdict,
        margin=margin,
        verification=_EXPERIMENTAL,
        issues=[_experimental_warning(citation, "combined skirt-transition stress adds pressure and bending")],
    )


@provable(ACI_318, "17.5 anchorage", "S7", verification=_EXPERIMENTAL)
def anchor_bolt_check(
    overturning_moment_nm: float,
    dead_weight_n: float,
    bolt_circle_diameter_m: float,
    num_bolts: int,
    provided_bolt_area_m2: float,
    allowable_tensile_stress_pa: float,
    editions: CodeEditions,
) -> Result:
    """Anchor-bolt tension and required root area from overturning (CO-2). EXPERIMENTAL.

    ``T_bolt = 4*M/(N*D) - W/N`` is the net uplift per bolt after the dead weight
    resists part of the moment; the required root area is ``T_bolt/f_allow``.
    A negative net tension means no uplift and no bolt area is required.
    """
    if overturning_moment_nm < 0:
        raise ValueError(f"overturning_moment_nm must be >= 0, got {overturning_moment_nm}")
    require_positive(W=dead_weight_n, D=bolt_circle_diameter_m, f_allow=allowable_tensile_stress_pa)
    require_positive(A_provided=provided_bolt_area_m2)
    if num_bolts < 2:
        raise ValueError(f"num_bolts must be >= 2, got {num_bolts}")
    net_tension = 4.0 * overturning_moment_nm / (num_bolts * bolt_circle_diameter_m) - dead_weight_n / num_bolts
    tension_per_bolt = max(0.0, net_tension)
    required_area = tension_per_bolt / allowable_tensile_stress_pa
    if required_area <= 0.0:
        verdict, margin = Verdict.PASS, None
    else:
        verdict, margin = margin_verdict(provided_bolt_area_m2, required_area)
    citation = citation_for(anchor_bolt_check, editions)
    return make_result(
        symbol="A_bolt_req",
        value=required_area,
        kind="area",
        formula="A_req = max(0, 4*M/(N*D) - W/N) / f_allow",
        substitutions={
            "M": format_value(overturning_moment_nm, "N*m"),
            "W": format_value(dead_weight_n, "N"),
            "D (bolt circle)": format_value(bolt_circle_diameter_m, "m"),
            "N": str(num_bolts),
            "tension per bolt": format_value(tension_per_bolt, "N"),
            "provided area": format_value(provided_bolt_area_m2, "m**2"),
            "f_allow": format_value(allowable_tensile_stress_pa, "Pa"),
        },
        citation=citation,
        inputs_used=[
            "bolt_circle_diameter_mm",
            "num_anchor_bolts",
            "provided_bolt_area_mm2",
            "allowable_bolt_tensile_mpa",
            "operating_weight_kg",
        ],
        verdict=verdict,
        margin=margin,
        verification=_EXPERIMENTAL,
        issues=[_experimental_warning(citation, "anchor tension uses a simplified bolt-circle overturning model")],
    )


@provable(ACI_318, "13.2 bearing", "S7", verification=_EXPERIMENTAL)
def base_plate_thickness(
    bearing_pressure_pa: float,
    plate_projection_m: float,
    allowable_bending_stress_pa: float,
    editions: CodeEditions,
) -> Result:
    """Cantilever base-plate thickness under bearing pressure (CO-2). EXPERIMENTAL.

    ``t = l*sqrt(3*p/S)`` treats the base plate as a unit-width cantilever of
    projection ``l`` under uniform bearing pressure ``p``.
    """
    require_positive(p=bearing_pressure_pa, l=plate_projection_m, S=allowable_bending_stress_pa)
    thickness = plate_projection_m * math.sqrt(3.0 * bearing_pressure_pa / allowable_bending_stress_pa)
    citation = citation_for(base_plate_thickness, editions)
    return make_result(
        symbol="t_bp",
        value=thickness,
        kind="length",
        formula="t = l*sqrt(3*p/S)  (cantilever base plate subset)",
        substitutions={
            "l (projection)": format_value(plate_projection_m, "m"),
            "p (bearing)": format_value(bearing_pressure_pa, "Pa"),
            "S (allowable)": format_value(allowable_bending_stress_pa, "Pa"),
        },
        citation=citation,
        inputs_used=[
            "base_plate_projection_mm",
            "foundation_bearing_pressure_kpa",
            "allowable_base_plate_bending_mpa",
        ],
        verification=_EXPERIMENTAL,
        issues=[_experimental_warning(citation, "base-plate thickness is a cantilever bending subset")],
    )


@provable(ASCE_7, "26.10 velocity pressure", "S8", verification=_EXPERIMENTAL)
def wind_velocity_pressure(
    wind_speed_m_s: float,
    exposure_factor_kz: float,
    topographic_factor_kzt: float,
    directionality_factor_kd: float,
    editions: CodeEditions,
) -> Result:
    """ASCE 7 velocity pressure ``qz = 0.613*Kz*Kzt*Kd*V^2`` (CO-3). EXPERIMENTAL.

    SI form (Pa with V in m/s). The ground-elevation factor is taken as 1.0.
    """
    require_positive(V=wind_speed_m_s, Kz=exposure_factor_kz, Kd=directionality_factor_kd)
    if topographic_factor_kzt <= 0:
        raise ValueError(f"topographic_factor_kzt must be > 0, got {topographic_factor_kzt}")
    velocity_pressure = 0.613 * exposure_factor_kz * topographic_factor_kzt * directionality_factor_kd * wind_speed_m_s**2
    citation = citation_for(wind_velocity_pressure, editions)
    return make_result(
        symbol="qz",
        value=velocity_pressure,
        kind="pressure",
        formula="qz = 0.613*Kz*Kzt*Kd*V^2  [Pa, V m/s]",
        substitutions={
            "V": format_value(wind_speed_m_s, "m/s"),
            "Kz": f"{exposure_factor_kz:g}",
            "Kzt": f"{topographic_factor_kzt:g}",
            "Kd": f"{directionality_factor_kd:g}",
        },
        citation=citation,
        inputs_used=[
            "wind_speed_m_s",
            "exposure_factor_kz",
            "topographic_factor_kzt",
            "directionality_factor_kd",
        ],
        verification=_EXPERIMENTAL,
        issues=[_experimental_warning(citation, "wind velocity pressure omits height-dependent Kz profile integration")],
    )


@provable(ASCE_7, "27.3 wind loads", "S8", verification=_EXPERIMENTAL)
def wind_base_moment(
    diameter_m: float,
    height_m: float,
    wind_speed_m_s: float,
    exposure_factor_kz: float,
    topographic_factor_kzt: float,
    directionality_factor_kd: float,
    editions: CodeEditions,
) -> Result:
    """Wind base moment on a cylindrical column (CO-3). EXPERIMENTAL.

    The velocity pressure at the reference height is applied to the projected
    area ``D*H`` with the resultant at mid-height, so ``M = 0.5*qz*D*H^2``.
    """
    require_positive(D=diameter_m, H=height_m)
    qz = wind_velocity_pressure(
        wind_speed_m_s,
        exposure_factor_kz,
        topographic_factor_kzt,
        directionality_factor_kd,
        editions,
    )
    moment = 0.5 * _number(qz) * diameter_m * height_m**2
    citation = citation_for(wind_base_moment, editions)
    return make_result(
        symbol="M_wind",
        value=moment,
        kind="moment",
        formula="M_wind = 0.5*qz*D*H^2  (resultant at mid-height)",
        substitutions={
            "qz": format_value(_number(qz), "Pa"),
            "D": format_value(diameter_m, "m"),
            "H": format_value(height_m, "m"),
        },
        citation=citation,
        inputs_used=[
            "inside_diameter_mm",
            "overall_height_mm",
            "wind_speed_m_s",
            "exposure_factor_kz",
            "topographic_factor_kzt",
            "directionality_factor_kd",
        ],
        children=[qz],
        verification=_EXPERIMENTAL,
        issues=[_experimental_warning(citation, "wind moment uses equivalent-static pressure at the reference height")],
    )


@provable(ASCE_7, "12.8 equivalent lateral force", "S8", verification=_EXPERIMENTAL)
def seismic_base_moment(
    seismic_response_coefficient_cs: float,
    seismic_weight_n: float,
    height_m: float,
    editions: CodeEditions,
) -> Result:
    """Seismic base shear and base moment (CO-3). EXPERIMENTAL.

    ``V = Cs*W`` and the base moment for an inverted-triangular lateral-force
    distribution is ``M = V*(2/3)*H``.
    """
    require_positive(Cs=seismic_response_coefficient_cs, W=seismic_weight_n, H=height_m)
    base_shear = seismic_response_coefficient_cs * seismic_weight_n
    moment = base_shear * (2.0 / 3.0) * height_m
    citation = citation_for(seismic_base_moment, editions)
    shear = make_result(
        symbol="V_seismic",
        value=base_shear,
        kind="force",
        formula="V = Cs*W",
        substitutions={
            "Cs": f"{seismic_response_coefficient_cs:g}",
            "W": format_value(seismic_weight_n, "N"),
        },
        citation=citation,
        verification=_EXPERIMENTAL,
    )
    return make_result(
        symbol="M_seismic",
        value=moment,
        kind="moment",
        formula="M_seismic = V*(2/3)*H  (inverted-triangular distribution)",
        substitutions={
            "Cs": f"{seismic_response_coefficient_cs:g}",
            "W": format_value(seismic_weight_n, "N"),
            "V": format_value(base_shear, "N"),
            "H": format_value(height_m, "m"),
        },
        citation=citation,
        inputs_used=["seismic_cs", "operating_weight_kg", "overall_height_mm"],
        children=[shear],
        verification=_EXPERIMENTAL,
        issues=[_experimental_warning(citation, "seismic moment assumes a simplified inverted-triangular distribution")],
    )


def _number(result: Result) -> float:
    """Return a result's numeric value, failing loudly if it produced none."""
    if result.value is None:
        raise ValueError(f"calculation {result.symbol!r} produced no numeric value")
    return result.value
