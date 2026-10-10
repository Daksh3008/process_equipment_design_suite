"""Heat-exchanger tubesheet and joint calculations — TEMA (HX-2, HX-3).

STATUS: EXPERIMENTAL (VAL-2).

* The tubesheet thickness uses the transparent TEMA-form bending expression
  ``t = F*G*sqrt(P/S) + CA`` where ``F`` is a boundary-condition factor and
  ``G`` the effective gasket diameter. This is a subset of the TEMA tubesheet
  rules; ASME VIII-1 UHX is the governing alternative for a full analysis and is
  flagged on every result.
* The tube layout reports the ligament efficiency ``e = (pitch - do)/pitch``.
* The tube-to-tubesheet joint check compares the pressure pull-out load with the
  capacity of a rolled or welded joint.

All quantities are internal SI: length in m, pressure and stress in Pa.
"""

from __future__ import annotations

import math

from ..core.calc import CodeEditions, citation_for, provable
from ..core.provenance import VerificationStatus
from ..core.result import Issue, Result, Severity
from ..core.standards import TEMA
from ..core.units import format_value
from .common import make_result, margin_verdict, require_positive

_EXPERIMENTAL = VerificationStatus.EXPERIMENTAL
_JOINT_TYPES = ("rolled", "welded")
_UHX_NOTE = (
    "TEMA tubesheet thickness is a transparent subset; ASME VIII-1 UHX "
    "(Part UHX) is the governing alternative for a full tubesheet analysis."
)


def _experimental_warning(citation, detail: str) -> Issue:
    """The disclosure every experimental heat-exchanger result carries (VAL-2)."""
    return Issue(
        severity=Severity.WARNING,
        message=f"Heat-exchanger calculation is EXPERIMENTAL in v1.5: {detail}",
        rationale=(
            "HX checks are not validated against worked examples in v1.5; verify "
            "against the licensed TEMA / ASME VIII-1 editions before use."
        ),
        citation=citation,
    )


@provable(TEMA, "R-6 tubesheet", "S6", verification=_EXPERIMENTAL)
def tubesheet_thickness(
    effective_gasket_diameter_m: float,
    design_pressure_pa: float,
    allowable_stress_pa: float,
    factor_f: float,
    editions: CodeEditions,
    corrosion_allowance_m: float = 0.0,
) -> Result:
    """Tubesheet thickness by a transparent TEMA-form expression (HX-2). EXPERIMENTAL.

    ``t = F*G*sqrt(P/S) + CA`` where ``G`` is the effective gasket diameter and
    ``F`` a dimensionless boundary-condition factor. UHX is referenced as the
    governing alternative in the attached warning.
    """
    require_positive(G=effective_gasket_diameter_m, P=design_pressure_pa, S=allowable_stress_pa, F=factor_f)
    if corrosion_allowance_m < 0:
        raise ValueError(f"corrosion_allowance_m must be >= 0, got {corrosion_allowance_m}")
    pressure_thickness = (
        factor_f * effective_gasket_diameter_m * math.sqrt(design_pressure_pa / allowable_stress_pa)
    )
    total = pressure_thickness + corrosion_allowance_m
    citation = citation_for(tubesheet_thickness, editions)
    child = make_result(
        symbol="t_tp",
        value=pressure_thickness,
        kind="length",
        formula="t_tp = F*G*sqrt(P/S)",
        substitutions={
            "F": f"{factor_f:g}",
            "G": format_value(effective_gasket_diameter_m, "m"),
            "P": format_value(design_pressure_pa, "Pa"),
            "S": format_value(allowable_stress_pa, "Pa"),
        },
        citation=citation,
        verification=_EXPERIMENTAL,
    )
    return make_result(
        symbol="t_tubesheet",
        value=total,
        kind="length",
        formula="t = F*G*sqrt(P/S) + CA  (transparent TEMA-form subset; UHX governs)",
        substitutions={
            "F": f"{factor_f:g}",
            "G": format_value(effective_gasket_diameter_m, "m"),
            "P": format_value(design_pressure_pa, "Pa"),
            "S": format_value(allowable_stress_pa, "Pa"),
            "CA": format_value(corrosion_allowance_m, "m"),
        },
        citation=citation,
        inputs_used=[
            "effective_gasket_diameter_m",
            "design_pressure_pa",
            "allowable_stress_pa",
            "tubesheet_factor_f",
            "corrosion_allowance_m",
        ],
        children=[child],
        verification=_EXPERIMENTAL,
        issues=[_experimental_warning(citation, _UHX_NOTE)],
    )


@provable(TEMA, "R-7.4 tube layout", "S6", verification=_EXPERIMENTAL)
def tube_layout(
    tube_outside_diameter_m: float,
    tube_pitch_m: float,
    editions: CodeEditions,
) -> Result:
    """Tube ligament efficiency for a triangular or square layout (HX-2). EXPERIMENTAL.

    ``e = (pitch - do)/pitch``; the pitch must exceed the tube outside diameter.
    """
    require_positive(do=tube_outside_diameter_m, pitch=tube_pitch_m)
    if tube_pitch_m <= tube_outside_diameter_m:
        raise ValueError(
            "tube pitch must exceed the tube outside diameter; "
            f"got pitch={tube_pitch_m} m, do={tube_outside_diameter_m} m"
        )
    efficiency = (tube_pitch_m - tube_outside_diameter_m) / tube_pitch_m
    citation = citation_for(tube_layout, editions)
    pitch_ratio = make_result(
        symbol="pitch_ratio",
        value=tube_pitch_m / tube_outside_diameter_m,
        kind="dimensionless",
        formula="pitch_ratio = pitch/do",
        substitutions={
            "pitch": format_value(tube_pitch_m, "m"),
            "do": format_value(tube_outside_diameter_m, "m"),
        },
        citation=citation,
        verification=_EXPERIMENTAL,
    )
    return make_result(
        symbol="e_ligament",
        value=efficiency,
        kind="dimensionless",
        formula="e = (pitch - do)/pitch",
        substitutions={
            "pitch": format_value(tube_pitch_m, "m"),
            "do": format_value(tube_outside_diameter_m, "m"),
            "e": f"{efficiency:.4g}",
        },
        citation=citation,
        inputs_used=["tube_outside_diameter_m", "tube_pitch_m"],
        children=[pitch_ratio],
        verification=_EXPERIMENTAL,
        issues=[_experimental_warning(citation, "ligament efficiency is reported for the entered pitch only")],
    )


@provable(TEMA, "R-8 tube-to-tubesheet joint", "S6", verification=_EXPERIMENTAL)
def tube_to_tubesheet_joint_check(
    tube_outside_diameter_m: float,
    tube_wall_thickness_m: float,
    design_pressure_pa: float,
    joint_type: str,
    joint_shear_strength_pa: float,
    editions: CodeEditions,
    joint_length_m: float = 0.0,
    weld_leg_m: float = 0.0,
) -> Result:
    """Tube-to-tubesheet joint strength: pull-out load vs joint capacity (HX-3).

    The axial pull-out load is taken as the pressure acting on the tube footprint,
    ``F = P*pi/4*do^2``. A rolled joint resists over its engagement length, a
    welded joint over the fillet-weld throat; the available capacity is
    ``tau_allow * shear_area``. The result carries an expansion-joint note.
    """
    require_positive(
        do=tube_outside_diameter_m,
        t=tube_wall_thickness_m,
        P=design_pressure_pa,
        tau=joint_shear_strength_pa,
    )
    if joint_type not in _JOINT_TYPES:
        raise ValueError(f"joint_type must be one of {_JOINT_TYPES}, got {joint_type!r}")
    if 2.0 * tube_wall_thickness_m >= tube_outside_diameter_m:
        raise ValueError(
            "tube wall thickness must be below half the tube outside diameter; "
            f"got t={tube_wall_thickness_m} m, do={tube_outside_diameter_m} m"
        )
    if joint_type == "rolled":
        if joint_length_m <= 0:
            raise ValueError(f"a rolled joint requires joint_length_m > 0, got {joint_length_m}")
        shear_area = math.pi * tube_outside_diameter_m * joint_length_m
        detail = "rolled joint over the engagement length"
    else:
        if weld_leg_m <= 0:
            raise ValueError(f"a welded joint requires weld_leg_m > 0, got {weld_leg_m}")
        throat = weld_leg_m / math.sqrt(2.0)
        shear_area = math.pi * tube_outside_diameter_m * throat
        detail = "welded joint over the fillet throat"
    pull_out = design_pressure_pa * math.pi / 4.0 * tube_outside_diameter_m**2
    capacity = joint_shear_strength_pa * shear_area
    verdict, margin = margin_verdict(capacity, pull_out)
    citation = citation_for(tube_to_tubesheet_joint_check, editions)
    return make_result(
        symbol="F_joint",
        value=capacity,
        kind="force",
        formula="F = tau*pi*do*L >= P*pi/4*do^2  (rolled: L=engagement; welded: L=throat)",
        substitutions={
            "do": format_value(tube_outside_diameter_m, "m"),
            "P": format_value(design_pressure_pa, "Pa"),
            "tau_allow": format_value(joint_shear_strength_pa, "Pa"),
            "shear area": format_value(shear_area, "m**2"),
            "pull-out load": format_value(pull_out, "N"),
            "capacity": format_value(capacity, "N"),
        },
        citation=citation,
        inputs_used=[
            "tube_outside_diameter_m",
            "tube_wall_thickness_m",
            "design_pressure_pa",
            "tube_joint_type",
            "tube_joint_shear_strength_mpa",
            "tube_joint_length_mm",
            "tube_weld_leg_mm",
        ],
        verdict=verdict,
        margin=margin,
        verification=_EXPERIMENTAL,
        issues=[
            _experimental_warning(citation, detail),
            Issue(
                severity=Severity.WARNING,
                message=(
                    "Thermal growth of the tube bundle is not checked; a fixed "
                    "tubesheet arrangement may require an expansion joint."
                ),
                rationale=(
                    "HX-5 thermal-growth sizing is deferred; provide an expansion "
                    "joint or a floating-head arrangement where differential growth "
                    "is significant."
                ),
                citation=citation,
            ),
        ],
    )
