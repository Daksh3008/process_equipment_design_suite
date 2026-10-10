"""MAWP determination — ASME VIII-1 UG-98.

The vessel MAWP is the least of the component MAWPs; the governing component is
reported so the user can see which part limits the vessel.
"""

from __future__ import annotations

import math

from ..core.calc import CodeEditions, citation_for, provable
from ..core.result import Result
from ..core.standards import ASME_VIII_1
from ..core.units import format_value
from .common import make_result


@provable(ASME_VIII_1, "UG-98", "S1")
def governing_mawp(
    component_mawps_pa: dict[str, float],
    editions: CodeEditions,
) -> Result:
    """Least component MAWP, naming the governing component."""
    if not component_mawps_pa:
        raise ValueError("at least one component MAWP is required")
    for name, value in component_mawps_pa.items():
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"component MAWP {name!r} must be finite and > 0, got {value}")
    governing_component = min(component_mawps_pa, key=lambda k: component_mawps_pa[k])
    mawp = component_mawps_pa[governing_component]
    return make_result(
        symbol="MAWP",
        value=mawp,
        kind="pressure",
        formula="MAWP = min(component MAWPs) [UG-98]",
        substitutions={name: format_value(value, "Pa") for name, value in component_mawps_pa.items()},
        citation=citation_for(governing_mawp, editions),
        inputs_used=list(component_mawps_pa),
        governing_case=governing_component,
    )
