"""Load cases and governing-case selection (CORE-7, UG-22).

A vessel is checked against a set of load cases. The governing internal-pressure
case is the non-test case with the highest pressure; the test case is tracked
separately and feeds the hydrostatic test calculation.
"""

from __future__ import annotations

from dataclasses import dataclass

_KNOWN_KINDS = {
    "operating",
    "unused",
    "test",
    "wind",
    "seismic",
    "seismic+operating",
    "maintenance",
}


@dataclass(frozen=True)
class LoadCase:
    """One design load case in internal SI units."""

    name: str
    pressure_pa: float
    temperature_c: float
    kind: str = "operating"

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("load case name must not be empty")
        if self.kind not in _KNOWN_KINDS:
            raise ValueError(f"unknown load case kind {self.kind!r}; known: {sorted(_KNOWN_KINDS)}")
        if self.pressure_pa < 0:
            raise ValueError(f"load case {self.name!r}: pressure must be >= 0, got {self.pressure_pa}")


class LoadCaseSet:
    """An ordered, non-empty collection of load cases."""

    def __init__(self, cases: list[LoadCase]) -> None:
        if not cases:
            raise ValueError("at least one load case is required")
        self._cases = list(cases)

    def __iter__(self):
        return iter(self._cases)

    def __len__(self) -> int:
        return len(self._cases)

    @property
    def cases(self) -> list[LoadCase]:
        return list(self._cases)

    def governing_internal(self) -> LoadCase:
        """Highest-pressure non-test case (governs pressure design)."""
        candidates = [c for c in self._cases if c.kind != "test"]
        if not candidates:
            raise ValueError("no non-test load case available to govern internal pressure")
        return max(candidates, key=lambda c: (c.pressure_pa, c.temperature_c))

    def test_case(self) -> LoadCase | None:
        """The test case, if any."""
        for case in self._cases:
            if case.kind == "test":
                return case
        return None
