"""Openings and reinforcement — ASME VIII-1 UG-36 through UG-41.

STATUS: EXPERIMENTAL. The area-replacement method is implemented in transparent
form: the required area is ``A = d * tr`` and the available area is the sum of
the excesses in the shell, nozzle wall and inward nozzle plus the weld area. The
coefficient-carrying variants of A1/A2/A3 in UG-37 are not reproduced; results
must be reviewed for configurations they do not cover.
"""

from __future__ import annotations

from ..core.calc import CodeEditions, citation_for, provable
from ..core.provenance import VerificationStatus
from ..core.result import Issue, Result, Severity
from ..core.standards import ASME_VIII_1
from ..core.units import format_value
from .common import make_result, margin_verdict, require_positive


def _experimental_warning(citation) -> Issue:
    """The disclosure every experimental opening result must carry (VAL-2)."""
    return Issue(
        severity=Severity.WARNING,
        message=(
            "Reinforcement uses a simplified area method; verify A1/A2/A3 coefficient "
            "variants and limits of reinforcement against the standard."
        ),
        rationale=(
            "Full UG-37 coefficient forms and the limits of reinforcement (2.5t / 2.5tn) "
            "are not reproduced; excess credit is clamped at zero for undersized parts."
        ),
        citation=citation,
    )


def _neck_experimental_warning(citation) -> Issue:
    """Disclosure for the nozzle-neck rule, which is a plain cylinder check."""
    return Issue(
        severity=Severity.WARNING,
        message=(
            "Nozzle-neck thickness is treated as a plain cylinder by UG-27(c)(1); "
            "verify the neck's own geometry, joint and reinforcement details."
        ),
        rationale="The neck is not a full UG-45/UG-37 combination check in v0.5.",
        citation=citation,
    )


@provable(ASME_VIII_1, "UG-37", "S1", verification=VerificationStatus.EXPERIMENTAL)
def required_reinforcement_area(
    opening_diameter_m: float,
    required_shell_thickness_m: float,
    editions: CodeEditions,
    factor_f: float = 1.0,
) -> Result:
    """Required reinforcement area ``A = d * tr * F`` (UG-37). EXPERIMENTAL."""
    require_positive(d=opening_diameter_m, tr=required_shell_thickness_m, F=factor_f)
    area = opening_diameter_m * required_shell_thickness_m * factor_f
    return make_result(
        symbol="A",
        value=area,
        kind="area",
        formula="A = d * tr * F",
        substitutions={
            "d": format_value(opening_diameter_m, "m"),
            "tr": format_value(required_shell_thickness_m, "m"),
            "F": f"{factor_f:g}",
        },
        citation=citation_for(required_reinforcement_area, editions),
        inputs_used=["opening_diameter_m", "required_shell_thickness_m", "factor_f"],
        verification=VerificationStatus.EXPERIMENTAL,
        issues=[_experimental_warning(citation_for(required_reinforcement_area, editions))],
    )


@provable(ASME_VIII_1, "UG-27(c)(1)", "S1", verification=VerificationStatus.EXPERIMENTAL)
def nozzle_neck_thickness(
    pressure_pa: float,
    opening_inside_radius_m: float,
    allowable_stress_pa: float,
    joint_efficiency: float,
    editions: CodeEditions,
    corrosion_allowance_m: float = 0.0,
) -> Result:
    """Required nozzle-neck pressure thickness, UG-27(c)(1) form. EXPERIMENTAL.

    The neck is treated as a small cylinder whose required wall follows the
    circumferential-joint equation. ``opening_inside_radius_m`` is half of the
    finished opening diameter ``d = OD - 2*tn_actual`` (or ``OD/2`` when no neck
    thickness is provided; ``d = OD`` is then the conservative opening).
    """
    require_positive(
        P=pressure_pa, R=opening_inside_radius_m, S=allowable_stress_pa, E=joint_efficiency
    )
    if corrosion_allowance_m < 0:
        raise ValueError(f"corrosion_allowance_m must be >= 0, got {corrosion_allowance_m}")
    denominator = allowable_stress_pa * joint_efficiency - 0.6 * pressure_pa
    if denominator <= 0:
        raise ValueError(
            "UG-27(c)(1) requires S*E > 0.6*P; "
            f"got S={allowable_stress_pa:g} Pa, E={joint_efficiency:g}, P={pressure_pa:g} Pa"
        )
    pressure_thickness = pressure_pa * opening_inside_radius_m / denominator
    total = pressure_thickness + corrosion_allowance_m
    return make_result(
        symbol="tn",
        value=total,
        kind="length",
        formula="tn = P*R/(S*E - 0.6*P) + CA",
        substitutions={
            "P": format_value(pressure_pa, "Pa"),
            "R": format_value(opening_inside_radius_m, "m"),
            "S": format_value(allowable_stress_pa, "Pa"),
            "E": f"{joint_efficiency:g}",
            "CA": format_value(corrosion_allowance_m, "m"),
        },
        citation=citation_for(nozzle_neck_thickness, editions),
        inputs_used=[
            "pressure_pa",
            "opening_inside_radius_m",
            "allowable_stress_pa",
            "joint_efficiency",
            "corrosion_allowance_m",
        ],
        verification=VerificationStatus.EXPERIMENTAL,
        issues=[_neck_experimental_warning(citation_for(nozzle_neck_thickness, editions))],
    )


@provable(ASME_VIII_1, "UG-37", "S1", verification=VerificationStatus.EXPERIMENTAL)
def nozzle_reinforcement_check(
    opening_diameter_m: float,
    required_shell_thickness_m: float,
    shell_excess_thickness_m: float,
    nozzle_excess_thickness_m: float,
    nozzle_projection_m: float,
    editions: CodeEditions,
    inward_nozzle_excess_thickness_m: float = 0.0,
    inward_nozzle_length_m: float = 0.0,
    weld_area_m2: float = 0.0,
) -> Result:
    """Area-replacement check for a single nozzle (UG-37). EXPERIMENTAL.

    ``shell_excess_thickness_m`` is (actual - required) shell thickness, and
    ``nozzle_excess_thickness_m`` is (actual - required) nozzle-wall thickness.
    """
    require_positive(
        d=opening_diameter_m,
        tr=required_shell_thickness_m,
        projection=nozzle_projection_m,
    )
    if min(shell_excess_thickness_m, nozzle_excess_thickness_m, inward_nozzle_excess_thickness_m) < 0:
        raise ValueError("excess thicknesses must be >= 0")
    if weld_area_m2 < 0:
        raise ValueError(f"weld_area_m2 must be >= 0, got {weld_area_m2}")

    required = opening_diameter_m * required_shell_thickness_m
    a1 = shell_excess_thickness_m * opening_diameter_m
    a2 = 2.0 * nozzle_excess_thickness_m * nozzle_projection_m
    a3 = 2.0 * inward_nozzle_excess_thickness_m * inward_nozzle_length_m
    available = a1 + a2 + a3 + weld_area_m2
    verdict, margin = margin_verdict(available, required)

    warning = _experimental_warning(citation_for(nozzle_reinforcement_check, editions))

    return make_result(
        symbol="A_avail",
        value=available,
        kind="area",
        formula="A_avail = A1 + A2 + A3 + A5;  A = d*tr",
        substitutions={
            "A (required)": format_value(required, "m**2"),
            "A1 (shell)": format_value(a1, "m**2"),
            "A2 (nozzle)": format_value(a2, "m**2"),
            "A3 (inward)": format_value(a3, "m**2"),
            "A5 (weld)": format_value(weld_area_m2, "m**2"),
        },
        citation=citation_for(nozzle_reinforcement_check, editions),
        inputs_used=[
            "opening_diameter_m",
            "required_shell_thickness_m",
            "shell_excess_thickness_m",
            "nozzle_excess_thickness_m",
            "nozzle_projection_m",
        ],
        verdict=verdict,
        margin=margin,
        verification=VerificationStatus.EXPERIMENTAL,
        issues=[warning],
    )
