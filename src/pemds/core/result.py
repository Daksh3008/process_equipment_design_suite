"""Result objects — the provenance-rich output of every calculation.

The GUI and the report engine are both renderers of these objects. A
:class:`Result` is a value in the calculation tree; a :class:`ResultTree` is the
full set of results for one equipment item and carries the governing case.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .provenance import Citation, VerificationStatus


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


class Verdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    NA = "na"


@dataclass
class Issue:
    """A validation or engineering issue attached to a result or an input."""

    severity: Severity
    message: str
    field: str | None = None
    rationale: str | None = None
    citation: Citation | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "severity": self.severity.value,
            "message": self.message,
            "field": self.field,
            "rationale": self.rationale,
            "citation": self.citation.to_dict() if self.citation else None,
        }


@dataclass
class Result:
    """A single calculated value with full provenance.

    ``value`` is stored in the internal SI base unit named by ``unit``; ``kind``
    lets a renderer convert to the user's display units at the edge. ``children``
    nests derived values (e.g. a component thickness under a vessel result).
    """

    symbol: str
    value: float | None
    unit: str
    kind: str
    formula: str
    substitutions: dict[str, str]
    citation: Citation
    inputs_used: list[str] = field(default_factory=list)
    verdict: Verdict = Verdict.NA
    margin: float | None = None
    governing_case: str | None = None
    verification: VerificationStatus = VerificationStatus.VERIFIED
    children: list[Result] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)

    def add(self, child: Result) -> Result:
        self.children.append(child)
        return child

    def flatten(self) -> list[Result]:
        """Depth-first list of this result and every descendant."""
        out: list[Result] = [self]
        for child in self.children:
            out.extend(child.flatten())
        return out

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "value": self.value,
            "unit": self.unit,
            "kind": self.kind,
            "formula": self.formula,
            "substitutions": dict(self.substitutions),
            "citation": self.citation.to_dict(),
            "inputs_used": list(self.inputs_used),
            "verdict": self.verdict.value,
            "margin": self.margin,
            "governing_case": self.governing_case,
            "verification": self.verification.value,
            "children": [c.to_dict() for c in self.children],
            "issues": [i.to_dict() for i in self.issues],
        }


@dataclass
class ResultTree:
    """All results for one equipment item."""

    name: str
    roots: list[Result] = field(default_factory=list)
    governing_case: str | None = None

    def add(self, result: Result) -> Result:
        self.roots.append(result)
        return result

    def flatten(self) -> list[Result]:
        out: list[Result] = []
        for root in self.roots:
            out.extend(root.flatten())
        return out

    def overall_verdict(self) -> Verdict:
        verdicts = {r.verdict for r in self.flatten()}
        if Verdict.FAIL in verdicts:
            return Verdict.FAIL
        if Verdict.WARN in verdicts:
            return Verdict.WARN
        if verdicts <= {Verdict.NA}:
            return Verdict.NA
        return Verdict.PASS

    def all_issues(self) -> list[Issue]:
        return [issue for r in self.flatten() for issue in r.issues]

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "governing_case": self.governing_case,
            "overall_verdict": self.overall_verdict().value,
            "roots": [r.to_dict() for r in self.roots],
        }


def worst_verdict(verdicts: list[Verdict]) -> Verdict:
    """Return the most severe verdict in *verdicts*; all-NA (or empty) is NA."""
    if Verdict.FAIL in verdicts:
        return Verdict.FAIL
    if Verdict.WARN in verdicts:
        return Verdict.WARN
    if any(v is Verdict.PASS for v in verdicts):
        return Verdict.PASS
    return Verdict.NA
