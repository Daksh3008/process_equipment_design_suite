"""External pressure — ASME VIII-1 UG-28 (cylindrical shells).

STATUS: EXPERIMENTAL. The full UG-28 procedure reads the geometry chart (factor
A) and the material chart (factor B). Both are figures in the standard and are
never reproduced here (spec section 6, decision D4). This module implements the
elastic long-cylinder relationship, which is the closed-form part of the
procedure, and states its assumption in the result. Design outside the elastic
range requires a transcribed chart dataset and must not rely on this module.

The algebra implemented here is exact and independently verifiable:

    A  = 1.1 / (Do/t)^2                       (elastic geometry approximation)
    B  = A * E / 2                            (elastic material line)
    Pa = 4 * B / (3 * (Do/t))  ==  2 * A * E / (3 * (Do/t))

The last identity is what makes ``B = A*E/2`` self-consistent with the standard's
two pressure equations.
"""

from __future__ import annotations

from ..core.calc import CodeEditions, citation_for, provable
from ..core.provenance import VerificationStatus
from ..core.result import Issue, Result, Severity
from ..core.standards import ASME_VIII_1
from ..core.units import format_value
from .common import make_result, require_positive


def factor_a_elastic_cylinder(do_t: float) -> float:
    """Elastic long-cylinder geometry factor ``A = 1.1/(Do/t)^2``."""
    if do_t < 10.0:
        raise ValueError(
            f"the external-pressure design charts apply for Do/t >= 10, got Do/t={do_t:g}"
        )
    return 1.1 / (do_t * do_t)


@provable(ASME_VIII_1, "UG-28(c)", "S1", verification=VerificationStatus.EXPERIMENTAL)
def external_pressure_cylinder(
    outside_diameter_m: float,
    unsupported_length_m: float,
    effective_thickness_m: float,
    modulus_pa: float,
    editions: CodeEditions,
) -> Result:
    """Allowable external pressure for a cylindrical shell (elastic range).

    EXPERIMENTAL: see the module docstring for the assumption.
    """
    require_positive(
        Do=outside_diameter_m,
        L=unsupported_length_m,
        t=effective_thickness_m,
        E=modulus_pa,
    )
    do_t = outside_diameter_m / effective_thickness_m
    l_do = unsupported_length_m / outside_diameter_m
    factor_a = factor_a_elastic_cylinder(do_t)
    factor_b = factor_a * modulus_pa / 2.0
    allowable = 4.0 * factor_b / (3.0 * do_t)

    warning = Issue(
        severity=Severity.WARNING,
        message=(
            "External-pressure allowable uses the elastic long-cylinder geometry "
            "approximation; results outside the elastic range are not valid."
        ),
        rationale=(
            "The standard's geometry/material charts are not reproduced; a "
            "transcribed numeric chart dataset is required for plastic-range design."
        ),
        citation=citation_for(external_pressure_cylinder, editions),
    )

    return make_result(
        symbol="Pa",
        value=allowable,
        kind="pressure",
        formula="A = 1.1/(Do/t)^2;  B = A*E/2;  Pa = 4*B/(3*(Do/t))",
        substitutions={
            "Do": format_value(outside_diameter_m, "m"),
            "L": format_value(unsupported_length_m, "m"),
            "t": format_value(effective_thickness_m, "m"),
            "Do/t": f"{do_t:.4g}",
            "L/Do": f"{l_do:.4g}",
            "A": f"{factor_a:.4g}",
            "B": format_value(factor_b, "Pa"),
            "E": format_value(modulus_pa, "Pa"),
        },
        citation=citation_for(external_pressure_cylinder, editions),
        inputs_used=[
            "outside_diameter_m",
            "unsupported_length_m",
            "effective_thickness_m",
            "modulus_pa",
        ],
        verification=VerificationStatus.EXPERIMENTAL,
        issues=[warning],
    )
