"""Vessel geometry constants shared across layers.

Pure facts about standard vessel head shapes and standard construction details
that the weight model, the 2D GA drawing and the 3D preview must all agree on —
one definition, several consumers, so the renderings of a single parameter set
cannot silently diverge (FR-3D, decision D3).
"""

from __future__ import annotations

from .result import ResultTree
from .units import from_base

#: Head depth as a fraction of the *inside* design diameter. The 2:1 ellipsoidal
#: head has an inside depth of D/4; hemispherical D/2; torispherical shares the
#: 2:1 depth for the GA outline; a flat head has none.
HEAD_DEPTH_FACTOR = {
    "ellipsoidal": 0.25,  # 2:1 head
    "torispherical": 0.25,
    "hemispherical": 0.5,
    "flat": 0.0,
}

#: Width of the skirt base plate beyond the shell outside radius, in mm.
#: The 2D GA's base line and the 3D preview's base plate show the same footprint.
SKIRT_BASE_OVERHANG_MM = 40.0


def required_shell_mm(tree: ResultTree) -> float:
    """Shell plate thickness in mm from the result tree (2D and 3D consumers)."""
    for result in tree.roots:
        if result.symbol == "t_shell" and result.value is not None:
            return from_base(result.value, "length", unit="mm")
    raise ValueError("result tree has no t_shell node from which to draw the shell thickness")


def provided_or_required_shell_mm(inputs, tree: ResultTree) -> float:
    """The shell thickness the geometry must use: provided plate, else required."""
    if inputs.provided_shell_thickness_mm is not None:
        return inputs.provided_shell_thickness_mm
    return required_shell_mm(tree)