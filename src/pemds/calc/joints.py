"""Joint efficiencies — ASME VIII-1 UW-12 / UW-11.

The values live in a provenance-stamped data file; this module only looks them
up. The table is loaded once at import into an immutable tuple, so the
calculation itself performs no I/O and is deterministic across calls.
"""

from __future__ import annotations

from ..core.calc import CodeEditions, citation_for, provable
from ..core.provenance import Provenance
from ..core.result import Issue, Result, Severity, Verdict
from ..core.standards import ASME_VIII_1
from ..data.loader import load_package_data
from .common import make_result

_RADIOGRAPHY = ("full", "spot", "none")


def _load_table() -> tuple[tuple[tuple[str, str, float, str], ...], Provenance]:
    data_file = load_package_data("codes/uw12_joint_efficiency.json")
    table = tuple(
        (
            str(row["joint_type"]),
            str(row["radiography"]),
            float(row["efficiency"]),
            str(row["description"]),
        )
        for row in data_file.data["joint_efficiencies"]
    )
    return table, data_file.provenance


#: Immutable lookup table: (joint_type, radiography, efficiency, description).
_JOINT_EFFICIENCY, _PROVENANCE = _load_table()


@provable(ASME_VIII_1, "UW-12", "S1")
def joint_efficiency(
    joint_type: str,
    radiography: str,
    editions: CodeEditions,
) -> Result:
    """Look up the joint efficiency E for a joint type and radiographic extent."""
    if radiography not in _RADIOGRAPHY:
        raise ValueError(f"radiography must be one of {_RADIOGRAPHY}, got {radiography!r}")
    for row_type, row_radiography, efficiency, description in _JOINT_EFFICIENCY:
        if row_type == str(joint_type) and row_radiography == radiography:
            result = make_result(
                symbol="E",
                value=efficiency,
                kind="dimensionless",
                formula="E = f(joint type, radiographic extent) [UW-12]",
                substitutions={
                    "joint type": str(joint_type),
                    "description": description,
                    "radiography": radiography,
                },
                citation=citation_for(joint_efficiency, editions),
                inputs_used=["joint_type", "radiography"],
                verdict=Verdict.NA,
            )
            if "UNVERIFIED" in _PROVENANCE.checked_by.upper():
                result.issues.append(
                    Issue(
                        severity=Severity.WARNING,
                        message=f"UW-12 joint-efficiency data is provisional ({_PROVENANCE.checked_by}).",
                        rationale=(
                            "Data policy: unreviewed data must not back a verified result."
                        ),
                        citation=citation_for(joint_efficiency, editions),
                    )
                )
            return result
    available = sorted({row_type for row_type, *_ in _JOINT_EFFICIENCY})
    raise ValueError(
        f"no UW-12 joint efficiency for joint_type={joint_type!r}, "
        f"radiography={radiography!r}; joint types available: {available}"
    )
