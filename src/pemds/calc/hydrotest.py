"""Hydrostatic / proof test — ASME VIII-1 UG-99.

The test pressure is based on the vessel MAWP and the ratio of the allowable
stress at the test temperature to the allowable stress at the design
temperature.
"""

from __future__ import annotations

from ..core.calc import CodeEditions, citation_for, provable
from ..core.result import Result
from ..core.standards import ASME_VIII_1
from ..core.units import format_value
from .common import make_result, require_positive

#: UG-99(b) minimum test factor.
TEST_FACTOR = 1.3


@provable(ASME_VIII_1, "UG-99(b)", "S1")
def hydrostatic_test_pressure(
    mawp_pa: float,
    allowable_stress_test_temp_pa: float,
    allowable_stress_design_temp_pa: float,
    editions: CodeEditions,
) -> Result:
    """Minimum hydrostatic test pressure, ``P_T = 1.3 * MAWP * S_T/S`` (UG-99(b))."""
    require_positive(
        MAWP=mawp_pa,
        S_T=allowable_stress_test_temp_pa,
        S=allowable_stress_design_temp_pa,
    )
    ratio = allowable_stress_test_temp_pa / allowable_stress_design_temp_pa
    test_pressure = TEST_FACTOR * mawp_pa * ratio
    return make_result(
        symbol="P_T",
        value=test_pressure,
        kind="pressure",
        formula="P_T = 1.3 * MAWP * (S_T / S)",
        substitutions={
            "MAWP": format_value(mawp_pa, "Pa"),
            "S_T": format_value(allowable_stress_test_temp_pa, "Pa"),
            "S": format_value(allowable_stress_design_temp_pa, "Pa"),
            "S_T/S": f"{ratio:.4g}",
        },
        citation=citation_for(hydrostatic_test_pressure, editions),
        inputs_used=[
            "mawp_pa",
            "allowable_stress_test_temp_pa",
            "allowable_stress_design_temp_pa",
        ],
    )
