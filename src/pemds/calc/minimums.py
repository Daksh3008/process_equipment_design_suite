"""Minimum thickness rules — ASME VIII-1 UG-16 and UG-45.

UG-16 gives the general minimum thickness of shells and heads. UG-45 gives the
minimum thickness of a nozzle neck as ``max(ta, min(tb, tc))``; ``ta`` is the
nozzle pressure thickness, ``tb`` follows the shell, and ``tc`` is tabulated by
nozzle size. The tabulated ``tc`` values are supplied by the caller (a
user-extensible data table), so the rule itself stays verifiable code.
"""

from __future__ import annotations

import math

from ..core.calc import CodeEditions, citation_for, provable
from ..core.result import Result
from ..core.standards import ASME_VIII_1
from ..core.units import format_value
from .common import make_result, require_positive

#: UG-16(b) general minimum thickness, exclusive of corrosion allowance.
UG16_MINIMUM_M = 0.0015  # 1.5 mm (1/16 in)


@provable(ASME_VIII_1, "UG-16(b)", "S1")
def minimum_shell_thickness(editions: CodeEditions) -> Result:
    """General minimum shell/head thickness from UG-16(b), exclusive of CA."""
    return make_result(
        symbol="t_min",
        value=UG16_MINIMUM_M,
        kind="length",
        formula="t_min = 1.5 mm (1/16 in), exclusive of corrosion allowance",
        substitutions={"t_min": format_value(UG16_MINIMUM_M, "m")},
        citation=citation_for(minimum_shell_thickness, editions),
        inputs_used=[],
    )


@provable(ASME_VIII_1, "UG-45", "S1")
def connection_minimum_thickness(
    ta_m: float,
    tb_m: float,
    tc_m: float,
    editions: CodeEditions,
) -> Result:
    """Minimum nozzle-neck thickness, ``tn = max(ta, min(tb, tc))`` (UG-45).

    ``ta`` = nozzle pressure thickness; ``tb`` = shell-based value; ``tc`` =
    tabulated value by nozzle size (user-supplied data table).
    """
    for name, value in (("ta_m", ta_m), ("tb_m", tb_m), ("tc_m", tc_m)):
        if not math.isfinite(value):
            raise ValueError(f"{name} must be finite, got {value}")
    require_positive(ta=ta_m, tb=tb_m)
    if tc_m < 0:
        raise ValueError(f"tc_m must be >= 0, got {tc_m}")
    tn = max(ta_m, min(tb_m, tc_m))
    return make_result(
        symbol="tn",
        value=tn,
        kind="length",
        formula="tn = max(ta, min(tb, tc))",
        substitutions={
            "ta": format_value(ta_m, "m"),
            "tb": format_value(tb_m, "m"),
            "tc": format_value(tc_m, "m"),
        },
        citation=citation_for(connection_minimum_thickness, editions),
        inputs_used=["ta_m", "tb_m", "tc_m"],
    )
