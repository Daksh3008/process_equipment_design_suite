"""Stiffening rings — ASME VIII-1 UG-29/UG-30 (external pressure).

STATUS: EXPERIMENTAL, mirroring :mod:`pemds.calc.external`. The standard's
procedure reads the geometry/material charts; this module implements the
closed-form elastic relationship, which is the documented expression for the
required moment of inertia of the combined ring-and-shell section:

    I_req = D_o^2 * L_s * (t + A_c/L_s) * A / 14

where ``A`` is the same elastic geometry factor used for UG-28. Design outside
the elastic range requires a transcribed chart dataset.
"""

from __future__ import annotations

from ..core.calc import CodeEditions, citation_for, provable
from ..core.provenance import VerificationStatus
from ..core.result import Issue, Result, Severity, Verdict
from ..core.standards import ASME_VIII_1
from ..core.units import format_value
from .common import make_result, margin_verdict, require_positive
from .external import factor_a_elastic_cylinder


@provable(ASME_VIII_1, "UG-29", "S1", verification=VerificationStatus.EXPERIMENTAL)
def stiffening_ring_check(
    outside_diameter_m: float,
    ring_spacing_m: float,
    shell_thickness_m: float,
    ring_section_area_m2: float,
    editions: CodeEditions,
    provided_inertia_m4: float | None = None,
) -> Result:
    """Required combined-section moment of inertia; pass/fail vs *provided_inertia_m4*.

    EXPERIMENTAL: uses the elastic geometry approximation (see module docstring).
    """
    require_positive(
        Do=outside_diameter_m,
        L_s=ring_spacing_m,
        t=shell_thickness_m,
        A_c=ring_section_area_m2,
    )
    if provided_inertia_m4 is not None and provided_inertia_m4 <= 0:
        raise ValueError(f"provided_inertia_m4 must be > 0, got {provided_inertia_m4}")

    do_t = outside_diameter_m / shell_thickness_m
    factor_a = factor_a_elastic_cylinder(do_t)
    effective_thickness = shell_thickness_m + ring_section_area_m2 / ring_spacing_m
    required_inertia = (
        outside_diameter_m ** 2 * ring_spacing_m * effective_thickness * factor_a / 14.0
    )

    warning = Issue(
        severity=Severity.WARNING,
        message=(
            "Stiffening-ring inertia uses the elastic geometry approximation; "
            "plastic-range design requires a transcribed chart dataset."
        ),
        rationale="The ASME geometry/material charts are never reproduced (decision D4).",
        citation=citation_for(stiffening_ring_check, editions),
    )
    verification = VerificationStatus.EXPERIMENTAL

    if provided_inertia_m4 is None:
        verdict, margin = Verdict.NA, None
    else:
        verdict, margin = margin_verdict(provided_inertia_m4, required_inertia)

    return make_result(
        symbol="I_req",
        value=required_inertia,
        kind="inertia",
        formula="I_req = Do^2 * L_s * (t + A_c/L_s) * A / 14",
        substitutions={
            "Do": format_value(outside_diameter_m, "m"),
            "L_s": format_value(ring_spacing_m, "m"),
            "t": format_value(shell_thickness_m, "m"),
            "A_c": format_value(ring_section_area_m2, "m**2"),
            "Do/t": f"{do_t:.4g}",
            "A": f"{factor_a:.4g}",
            **({"I_provided": format_value(provided_inertia_m4, "m**4")} if provided_inertia_m4 is not None else {}),
        },
        citation=citation_for(stiffening_ring_check, editions),
        inputs_used=[
            "outside_diameter_m",
            "ring_spacing_m",
            "shell_thickness_m",
            "ring_section_area_m2",
        ],
        verdict=verdict,
        margin=margin,
        verification=verification,
        issues=[warning],
    )