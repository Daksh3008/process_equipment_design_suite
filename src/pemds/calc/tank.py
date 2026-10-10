"""Storage-tank calculations — API 650 (TK-1..TK-3). EXPERIMENTAL (VAL-2).

STATUS: EXPERIMENTAL. The tank checks are transparent subsets of API 650:

* the shell-course thickness uses the one-foot method form
  ``t = 4.9*D*(H-0.3)*G/(S*E) + CA``, with the published unit convention
  (t, CA mm; D, H m; S MPa; G, E dimensionless);
* the roof sizing is a preliminary plate/membrane estimate, not the API 650
  supported-roof structural design;
* the opening check is the simple area-replacement subset ``A = d*tr``.

None of these results are validated against worked examples in v1.5; verify
against the licensed edition before use.
"""

from __future__ import annotations

import math

from ..core.calc import CodeEditions, citation_for, provable
from ..core.provenance import VerificationStatus
from ..core.result import Issue, Result, Severity
from ..core.standards import API_650
from ..core.units import format_value
from .common import make_result, margin_verdict, require_positive

_EXPERIMENTAL = VerificationStatus.EXPERIMENTAL
_ROOF_TYPES = ("cone", "dome", "floating")
_POISSON = 0.3


def _experimental_warning(citation, detail: str) -> Issue:
    """The disclosure every experimental tank result carries (VAL-2)."""
    return Issue(
        severity=Severity.WARNING,
        message=(
            "Storage-tank calculation is EXPERIMENTAL in v1.5 and uses a transparent "
            f"API 650 subset: {detail}"
        ),
        rationale=(
            "TK checks are not validated against worked examples in v1.5; an "
            "independent check against the licensed edition is required."
        ),
        citation=citation,
    )


@provable(API_650, "5.6 shell design", "S5", verification=_EXPERIMENTAL)
def shell_course_thickness(
    diameter_m: float,
    liquid_height_m: float,
    specific_gravity: float,
    allowable_stress_pa: float,
    joint_efficiency: float,
    editions: CodeEditions,
    corrosion_allowance_m: float = 0.0,
) -> Result:
    """Required shell-course thickness by the API 650 one-foot method (TK-1).

    Implements ``t = 4.9*D*(H-0.3)*G/(S*E) + CA`` in the published SI convention:
    ``t`` and ``CA`` in mm, ``D`` and ``H`` in m, ``S`` in MPa, ``G`` and ``E``
    dimensionless. The returned value is converted to metres for the SI base.
    """
    require_positive(
        D=diameter_m,
        H=liquid_height_m,
        G=specific_gravity,
        S=allowable_stress_pa,
        E=joint_efficiency,
    )
    if corrosion_allowance_m < 0:
        raise ValueError(f"corrosion_allowance_m must be >= 0, got {corrosion_allowance_m}")
    if liquid_height_m <= 0.3:
        raise ValueError(
            "the one-foot method requires a design liquid height above 0.3 m; "
            f"got {liquid_height_m}"
        )
    stress_mpa = allowable_stress_pa / 1.0e6
    pressure_mm = (
        4.9 * diameter_m * (liquid_height_m - 0.3) * specific_gravity / (stress_mpa * joint_efficiency)
    )
    total_mm = pressure_mm + corrosion_allowance_m * 1000.0
    citation = citation_for(shell_course_thickness, editions)
    child = make_result(
        symbol="t_p",
        value=pressure_mm / 1000.0,
        kind="length",
        formula="t_p = 4.9*D*(H-0.3)*G/(S*E)  [t_p mm; D,H m; S MPa]",
        substitutions={
            "D": format_value(diameter_m, "m"),
            "H-0.3": format_value(liquid_height_m - 0.3, "m"),
            "G": f"{specific_gravity:g}",
            "S": format_value(allowable_stress_pa, "Pa"),
            "E": f"{joint_efficiency:g}",
        },
        citation=citation,
        inputs_used=[
            "diameter_m",
            "liquid_height_m",
            "specific_gravity",
            "allowable_stress_pa",
            "joint_efficiency",
        ],
        verification=_EXPERIMENTAL,
    )
    return make_result(
        symbol="t_shell",
        value=total_mm / 1000.0,
        kind="length",
        formula="t = 4.9*D*(H-0.3)*G/(S*E) + CA  [t,CA mm; D,H m; S MPa; G,E -]",
        substitutions={
            "D": format_value(diameter_m, "m"),
            "H": format_value(liquid_height_m, "m"),
            "G": f"{specific_gravity:g}",
            "S": format_value(allowable_stress_pa, "Pa"),
            "E": f"{joint_efficiency:g}",
            "CA": format_value(corrosion_allowance_m, "m"),
            "t (mm)": f"{total_mm:g} mm",
        },
        citation=citation,
        inputs_used=[
            "diameter_m",
            "liquid_height_m",
            "specific_gravity",
            "allowable_stress_pa",
            "joint_efficiency",
            "corrosion_allowance_m",
        ],
        children=[child],
        verification=_EXPERIMENTAL,
        issues=[
            _experimental_warning(
                citation, "the one-foot shell method only; variable design and seismic shell rules are not covered"
            )
        ],
    )


@provable(API_650, "5.6 shell design", "S5", verification=_EXPERIMENTAL)
def shell_courses(
    diameter_m: float,
    design_liquid_height_m: float,
    plate_width_m: float,
    specific_gravity: float,
    allowable_stress_pa: float,
    joint_efficiency: float,
    editions: CodeEditions,
    corrosion_allowance_m: float = 0.0,
    provided_thickness_m: float | None = None,
    design_head_offset_m: float = 0.3,
) -> Result:
    """Course-by-course shell thickness down a tank (TK-1, v1.5 plate layout).

    Each course is one plate wide (``plate_width_m``). The one-foot method is
    applied at a design point ``design_head_offset_m`` (0.3 m) above the bottom
    of the course, so the bottom course is thickest and the top thinnest as the
    hydrostatic head falls. For each course the result also reports the maximum
    liquid level it can sustain for the provided plate thickness and the
    corresponding static pressure.
    """
    require_positive(
        D=diameter_m,
        H=design_liquid_height_m,
        w=plate_width_m,
        G=specific_gravity,
        S=allowable_stress_pa,
        E=joint_efficiency,
    )
    if corrosion_allowance_m < 0:
        raise ValueError(f"corrosion_allowance_m must be >= 0, got {corrosion_allowance_m}")
    if design_head_offset_m < 0:
        raise ValueError(f"design_head_offset_m must be >= 0, got {design_head_offset_m}")
    if provided_thickness_m is not None and provided_thickness_m <= corrosion_allowance_m:
        raise ValueError("provided thickness must exceed the corrosion allowance")

    stress_mpa = allowable_stress_pa / 1.0e6
    corrosion_mm = corrosion_allowance_m * 1000.0
    n_courses = max(1, math.ceil(design_liquid_height_m / plate_width_m))
    citation = citation_for(shell_courses, editions)
    children: list[Result] = []
    governing_mm = 0.0

    for index in range(n_courses):
        z_low = index * plate_width_m
        head = max(0.0, design_liquid_height_m - z_low - design_head_offset_m)
        pressure_mm = 4.9 * diameter_m * head * specific_gravity / (stress_mpa * joint_efficiency)
        required_mm = pressure_mm + corrosion_mm
        governing_mm = max(governing_mm, required_mm)
        # Capacity: the liquid level this course sustains for the supplied plate.
        available_mm = (
            provided_thickness_m * 1000.0 if provided_thickness_m is not None else required_mm
        ) - corrosion_mm
        available_mm = max(0.0, available_mm)
        capacity_head_m = available_mm * stress_mpa * joint_efficiency / (
            4.9 * diameter_m * specific_gravity
        )
        h_max = z_low + design_head_offset_m + capacity_head_m
        p_max = specific_gravity * 1000.0 * 9.80665 * capacity_head_m
        children.append(
            make_result(
                symbol=f"t_c{index + 1}",
                value=required_mm / 1000.0,
                kind="length",
                formula="t_course = 4.9*D*(H - z_low - 0.3)*G/(S*E) + CA",
                substitutions={
                    "course": f"{index + 1} of {n_courses}",
                    "bottom elevation": format_value(z_low, "m"),
                    "design head": format_value(head, "m"),
                    "max liquid level": format_value(h_max, "m"),
                    "max static pressure": format_value(p_max, "Pa"),
                },
                citation=citation,
                inputs_used=["diameter_m", "design_liquid_height_m", "plate_width_m"],
                verification=_EXPERIMENTAL,
            )
        )

    return make_result(
        symbol="t_shell",
        value=governing_mm / 1000.0,
        kind="length",
        formula="t_shell = max over courses of 4.9*D*(H - z_low - 0.3)*G/(S*E) + CA",
        substitutions={
            "D": format_value(diameter_m, "m"),
            "H": format_value(design_liquid_height_m, "m"),
            "plate width": format_value(plate_width_m, "m"),
            "courses": str(n_courses),
            "G": f"{specific_gravity:g}",
            "S": format_value(allowable_stress_pa, "Pa"),
            "E": f"{joint_efficiency:g}",
            "CA": format_value(corrosion_allowance_m, "m"),
        },
        citation=citation,
        inputs_used=[
            "diameter_m",
            "design_liquid_height_m",
            "plate_width_m",
            "specific_gravity",
            "allowable_stress_pa",
            "joint_efficiency",
            "corrosion_allowance_m",
        ],
        children=children,
        verification=_EXPERIMENTAL,
        issues=[
            _experimental_warning(
                citation,
                "course-by-course one-foot shell method; variable-design and seismic shell rules are not covered",
            )
        ],
    )


@provable(API_650, "5.6 shell design", "S5", verification=_EXPERIMENTAL)
def plate_quantities(
    diameter_m: float,
    design_liquid_height_m: float,
    plate_width_m: float,
    plate_length_m: float,
    editions: CodeEditions,
) -> Result:
    """Plate count and arrangement for the cylindrical shell (TK-1, v1.5).

    ``N_courses = ceil(H / plate_width)`` and
    ``plates_per_course = ceil(pi*D / plate_length)``. Vertical joints of
    successive courses are staggered ("zig-zag") by half a plate length.
    """
    require_positive(D=diameter_m, H=design_liquid_height_m, w=plate_width_m, L=plate_length_m)
    n_courses = max(1, math.ceil(design_liquid_height_m / plate_width_m))
    circumference = math.pi * diameter_m
    plates_per_course = max(1, math.ceil(circumference / plate_length_m))
    total = n_courses * plates_per_course
    stagger = plate_length_m / 2.0
    citation = citation_for(plate_quantities, editions)

    children = [
        make_result(
            symbol="N_courses",
            value=float(n_courses),
            kind="dimensionless",
            formula="N_courses = ceil(H / plate_width)",
            substitutions={
                "H": format_value(design_liquid_height_m, "m"),
                "plate width": format_value(plate_width_m, "m"),
            },
            citation=citation,
            verification=_EXPERIMENTAL,
        ),
        make_result(
            symbol="plates_per_course",
            value=float(plates_per_course),
            kind="dimensionless",
            formula="plates_per_course = ceil(pi*D / plate_length)",
            substitutions={
                "circumference": format_value(circumference, "m"),
                "plate length": format_value(plate_length_m, "m"),
            },
            citation=citation,
            verification=_EXPERIMENTAL,
        ),
        make_result(
            symbol="stagger_offset",
            value=stagger,
            kind="length",
            formula="stagger_offset = plate_length / 2 (vertical joints zig-zag between courses)",
            substitutions={"plate length": format_value(plate_length_m, "m")},
            citation=citation,
            verification=_EXPERIMENTAL,
        ),
    ]
    return make_result(
        symbol="N_plates",
        value=float(total),
        kind="dimensionless",
        formula="N_plates = N_courses * ceil(pi*D / plate_length)",
        substitutions={
            "D": format_value(diameter_m, "m"),
            "H": format_value(design_liquid_height_m, "m"),
            "plate width": format_value(plate_width_m, "m"),
            "plate length": format_value(plate_length_m, "m"),
            "arrangement": "vertical joints staggered by half a plate length between courses",
        },
        citation=citation,
        inputs_used=["diameter_m", "design_liquid_height_m", "plate_width_m", "plate_length_m"],
        children=children,
        verification=_EXPERIMENTAL,
        issues=[
            _experimental_warning(
                citation,
                "plate count is a rectangular-course take-off; nozzle cut-outs, door sheets and shell openings are not deducted",
            )
        ],
    )


@provable(API_650, "5.10 roof design", "S5", verification=_EXPERIMENTAL)
def roof_sizing(
    roof_type: str,
    diameter_m: float,
    slope_ratio: float,
    dome_rise_m: float,
    live_load_pa: float,
    dead_load_pa: float,
    allowable_stress_pa: float,
    editions: CodeEditions,
    corrosion_allowance_m: float = 0.0,
) -> Result:
    """Preliminary roof geometry and plate sizing for the selected roof type (TK-2).

    Cone roofs use a simply-supported plate bending subset; dome roofs use a
    spherical membrane subset; floating roofs report a deck concept and no fixed
    plate thickness. ``slope_ratio`` is rise/run for a cone roof.
    """
    if roof_type not in _ROOF_TYPES:
        raise ValueError(f"roof_type must be one of {_ROOF_TYPES}, got {roof_type!r}")
    require_positive(D=diameter_m, S=allowable_stress_pa)
    if slope_ratio <= 0:
        raise ValueError(f"slope_ratio must be > 0, got {slope_ratio}")
    if min(live_load_pa, dead_load_pa) < 0:
        raise ValueError("roof loads must be >= 0")
    if corrosion_allowance_m < 0:
        raise ValueError(f"corrosion_allowance_m must be >= 0, got {corrosion_allowance_m}")

    radius = diameter_m / 2.0
    load = live_load_pa + dead_load_pa
    citation = citation_for(roof_sizing, editions)
    children: list[Result] = []
    substitutions: dict[str, str] = {
        "roof type": roof_type,
        "D": format_value(diameter_m, "m"),
        "q (live + dead)": format_value(load, "Pa"),
        "S": format_value(allowable_stress_pa, "Pa"),
        "CA": format_value(corrosion_allowance_m, "m"),
    }

    if roof_type == "cone":
        theta = math.atan(slope_ratio)
        slant = radius / math.cos(theta)
        factor = 3.0 * (3.0 + _POISSON) / 8.0
        pressure_thickness = radius * math.sqrt(factor * load / allowable_stress_pa)
        formula = "t = R*sqrt(3*(3+nu)*q/(8*S)) + CA  (cone plate subset, nu=0.3)"
        children.append(
            make_result(
                symbol="theta_roof",
                value=math.degrees(theta),
                kind="angle",
                formula="theta = atan(slope_ratio)",
                substitutions={"slope_ratio": f"{slope_ratio:g}"},
                citation=citation,
                verification=_EXPERIMENTAL,
            )
        )
        substitutions["slope angle"] = f"{math.degrees(theta):g} deg"
        substitutions["slant length"] = format_value(slant, "m")
    elif roof_type == "dome":
        if not 0.0 < dome_rise_m < radius:
            raise ValueError(
                f"dome_rise_m must lie in (0, D/2); got {dome_rise_m} m for a radius of {radius} m"
            )
        dome_radius = (radius**2 + dome_rise_m**2) / (2.0 * dome_rise_m)
        pressure_thickness = load * dome_radius / (2.0 * allowable_stress_pa)
        formula = "t = q*R_dome/(2*S) + CA;  R_dome = (R^2 + h^2)/(2*h)  (dome membrane subset)"
        children.append(
            make_result(
                symbol="R_dome",
                value=dome_radius,
                kind="length",
                formula="R_dome = (R^2 + h^2)/(2*h)",
                substitutions={
                    "R": format_value(radius, "m"),
                    "h": format_value(dome_rise_m, "m"),
                },
                citation=citation,
                verification=_EXPERIMENTAL,
            )
        )
        substitutions["dome radius"] = format_value(dome_radius, "m")
        substitutions["dome rise"] = format_value(dome_rise_m, "m")
    else:  # floating
        pressure_thickness = 0.0
        formula = "t = 0 (floating roof deck sizing not modelled; concept reported only)"

    total = pressure_thickness + corrosion_allowance_m
    return make_result(
        symbol="t_roof",
        value=total,
        kind="length",
        formula=formula,
        substitutions=substitutions,
        citation=citation,
        inputs_used=[
            "roof_type",
            "diameter_m",
            "slope_ratio",
            "dome_rise_m",
            "roof_live_load_kpa",
            "roof_dead_load_kpa",
            "allowable_stress_pa",
        ],
        children=children,
        verification=_EXPERIMENTAL,
        issues=[
            _experimental_warning(
                citation, "roof sizing is a preliminary plate/membrane estimate, not the supported-roof design"
            )
        ],
    )


@provable(API_650, "5.7 openings", "S5", verification=_EXPERIMENTAL)
def opening_reinforcement_check(
    opening_diameter_m: float,
    required_shell_thickness_m: float,
    shell_excess_thickness_m: float,
    nozzle_excess_thickness_m: float,
    projection_m: float,
    editions: CodeEditions,
) -> Result:
    """Simple area-replacement check for a tank shell opening (TK-3). EXPERIMENTAL.

    ``A = d*tr`` and ``A_avail = A1 + A2`` with ``A1`` the shell excess and ``A2``
    twice the nozzle excess over the projection. This is the transparent subset of
    the API 650 5.7 area rules; the coefficient forms are not reproduced.
    """
    require_positive(d=opening_diameter_m, tr=required_shell_thickness_m, projection=projection_m)
    if min(shell_excess_thickness_m, nozzle_excess_thickness_m) < 0:
        raise ValueError("excess thicknesses must be >= 0")
    required = opening_diameter_m * required_shell_thickness_m
    a1 = shell_excess_thickness_m * opening_diameter_m
    a2 = 2.0 * nozzle_excess_thickness_m * projection_m
    available = a1 + a2
    verdict, margin = margin_verdict(available, required)
    citation = citation_for(opening_reinforcement_check, editions)
    return make_result(
        symbol="A_avail",
        value=available,
        kind="area",
        formula="A_avail = A1 + A2 >= A = d*tr  (API 650 5.7 area subset)",
        substitutions={
            "d (opening)": format_value(opening_diameter_m, "m"),
            "tr (shell)": format_value(required_shell_thickness_m, "m"),
            "A (required)": format_value(required, "m**2"),
            "A1 (shell excess)": format_value(a1, "m**2"),
            "A2 (nozzle excess)": format_value(a2, "m**2"),
            "projection": format_value(projection_m, "m"),
        },
        citation=citation,
        inputs_used=[
            "opening_diameter_m",
            "required_shell_thickness_m",
            "shell_excess_thickness_m",
            "nozzle_excess_thickness_m",
            "projection_m",
        ],
        verdict=verdict,
        margin=margin,
        verification=_EXPERIMENTAL,
        issues=[
            _experimental_warning(
                citation, "opening reinforcement is the simple A = d*tr area subset"
            )
        ],
    )
