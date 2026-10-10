"""Piping calculations — ASME B31.3 (PS-1, PS-2).

Straight-pipe wall thickness per 304.1.2 and its MAWP inversion, plus a
simplified branch reinforcement check per 304.3 (EXPERIMENTAL).
"""

from __future__ import annotations

from ..core.calc import CodeEditions, citation_for, provable
from ..core.provenance import VerificationStatus
from ..core.result import Issue, Result, Severity
from ..core.standards import ASME_B31_3
from ..core.units import format_value
from .common import make_result, margin_verdict, require_positive


@provable(ASME_B31_3, "304.1.2", "S4")
def straight_pipe_thickness(
    pressure_pa: float,
    outside_diameter_m: float,
    allowable_stress_pa: float,
    joint_efficiency: float,
    y_factor: float,
    editions: CodeEditions,
    corrosion_allowance_m: float = 0.0,
    mill_tolerance_pct: float = 0.0,
) -> Result:
    """Required straight-pipe wall thickness, ``t = P*D/(2*(S*E + P*Y)) + CA``.

    The nominal wall divides by (1 - mill tolerance), so the tolerance works in
    the conservative direction.
    """
    require_positive(
        P=pressure_pa, D=outside_diameter_m, S=allowable_stress_pa, E=joint_efficiency
    )
    if not 0.0 <= y_factor <= 1.0:
        raise ValueError(f"y_factor must lie in [0, 1], got {y_factor}")
    if corrosion_allowance_m < 0:
        raise ValueError(f"corrosion_allowance_m must be >= 0, got {corrosion_allowance_m}")
    if not 0.0 <= mill_tolerance_pct < 100.0:
        raise ValueError(f"mill_tolerance_pct must be in [0, 100), got {mill_tolerance_pct}")
    denominator = 2.0 * (allowable_stress_pa * joint_efficiency + pressure_pa * y_factor)
    if denominator <= 0:
        raise ValueError(
            f"B31.3 304.1.2 requires S*E + P*Y > 0; got S={allowable_stress_pa:g}, "
            f"E={joint_efficiency:g}, P={pressure_pa:g}, Y={y_factor:g}"
        )
    pressure_thickness = pressure_pa * outside_diameter_m / denominator
    total = pressure_thickness + corrosion_allowance_m
    nominal = total / (1.0 - mill_tolerance_pct / 100.0)
    child = make_result(
        symbol="t_p",
        value=pressure_thickness,
        kind="length",
        formula="t_p = P*D/(2*(S*E + P*Y))",
        substitutions={
            "P": format_value(pressure_pa, "Pa"),
            "D": format_value(outside_diameter_m, "m"),
            "S": format_value(allowable_stress_pa, "Pa"),
            "E": f"{joint_efficiency:g}",
            "Y": f"{y_factor:g}",
        },
        citation=citation_for(straight_pipe_thickness, editions),
    )
    return make_result(
        symbol="t",
        value=nominal,
        kind="length",
        formula="t = (P*D/(2*(S*E + P*Y)) + CA)/(1 - tol)",
        substitutions={
            "P": format_value(pressure_pa, "Pa"),
            "D": format_value(outside_diameter_m, "m"),
            "S": format_value(allowable_stress_pa, "Pa"),
            "E": f"{joint_efficiency:g}",
            "Y": f"{y_factor:g}",
            "CA": format_value(corrosion_allowance_m, "m"),
            "tol": f"{mill_tolerance_pct:g}%",
        },
        citation=citation_for(straight_pipe_thickness, editions),
        inputs_used=["pressure_pa", "outside_diameter_m", "allowable_stress_pa", "joint_efficiency"],
        children=[child],
    )


@provable(ASME_B31_3, "304.1.2", "S4")
def pipe_mawp(
    net_wall_m: float,
    outside_diameter_m: float,
    allowable_stress_pa: float,
    joint_efficiency: float,
    y_factor: float,
    editions: CodeEditions,
) -> Result:
    """Maximum allowable working pressure for a pipe wall, net of corrosion."""
    require_positive(
        t=net_wall_m, D=outside_diameter_m, S=allowable_stress_pa, E=joint_efficiency
    )
    if not 0.0 <= y_factor <= 1.0:
        raise ValueError(f"y_factor must lie in [0, 1], got {y_factor}")
    denominator = outside_diameter_m - 2.0 * y_factor * net_wall_m
    if denominator <= 0:
        raise ValueError(
            f"B31.3 inversion requires D > 2*Y*t; got D={outside_diameter_m:g} m, "
            f"Y={y_factor:g}, t={net_wall_m:g} m"
        )
    mawp = 2.0 * allowable_stress_pa * joint_efficiency * net_wall_m / denominator
    return make_result(
        symbol="P",
        value=mawp,
        kind="pressure",
        formula="P = 2*S*E*t/(D - 2*Y*t)",
        substitutions={
            "S": format_value(allowable_stress_pa, "Pa"),
            "E": f"{joint_efficiency:g}",
            "t": format_value(net_wall_m, "m"),
            "D": format_value(outside_diameter_m, "m"),
            "Y": f"{y_factor:g}",
        },
        citation=citation_for(pipe_mawp, editions),
        inputs_used=["net_wall_m", "outside_diameter_m", "allowable_stress_pa", "joint_efficiency"],
    )


@provable(ASME_B31_3, "304.3", "S4", verification=VerificationStatus.EXPERIMENTAL)
def branch_reinforcement_check(
    branch_outside_diameter_m: float,
    required_pipe_thickness_m: float,
    run_excess_thickness_m: float,
    branch_excess_thickness_m: float,
    editions: CodeEditions,
) -> Result:
    """Simple area check for a branch connection (B31.3 304.3). EXPERIMENTAL.

    ``required_pipe_thickness_m`` is the run-pipe pressure thickness; excesses are
    (actual - required) thicknesses. This is a transparent subset of 304.3's area
    rules and must be reviewed for covered configurations.
    """
    require_positive(
        d=branch_outside_diameter_m, tr=required_pipe_thickness_m
    )
    if min(run_excess_thickness_m, branch_excess_thickness_m) < 0:
        raise ValueError("excess thicknesses must be >= 0")
    required_area = branch_outside_diameter_m * required_pipe_thickness_m
    available = (run_excess_thickness_m) * branch_outside_diameter_m  # Shell excess only
    verdict, margin = margin_verdict(available, required_area)
    return make_result(
        symbol="A_avail",
        value=available,
        kind="area",
        formula="A_avail = (t_run - tr) * d_branch;  A_req = d_branch * tr",
        substitutions={
            "A (required)": format_value(required_area, "m**2"),
            "A1 (run pipe excess)": format_value(available, "m**2"),
        },
        citation=citation_for(branch_reinforcement_check, editions),
        inputs_used=["branch_outside_diameter_m", "required_pipe_thickness_m"],
        verdict=verdict,
        margin=margin,
        verification=VerificationStatus.EXPERIMENTAL,
        issues=[
            Issue(
                severity=Severity.WARNING,
                message="Branch reinforcement uses a simplified 304.3 area subset.",
                rationale="Full weld/branch area terms are not implemented.",
                citation=citation_for(branch_reinforcement_check, editions),
            )
        ],
    )