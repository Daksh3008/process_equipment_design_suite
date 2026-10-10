"""Shared helpers for calculation modules."""

from __future__ import annotations

import math
from collections.abc import Iterable

from ..core.provenance import Citation, VerificationStatus
from ..core.result import Issue, Result, ResultTree, Verdict
from ..core.units import base_unit


def make_result(
    *,
    symbol: str,
    value: float | None,
    kind: str,
    formula: str,
    substitutions: dict[str, str],
    citation: Citation,
    unit: str | None = None,
    inputs_used: Iterable[str] = (),
    verdict: Verdict = Verdict.NA,
    margin: float | None = None,
    governing_case: str | None = None,
    verification: VerificationStatus = VerificationStatus.VERIFIED,
    children: Iterable[Result] | None = None,
    issues: Iterable[Issue] | None = None,
) -> Result:
    """Build a :class:`Result` with the internal SI base unit for *kind*."""
    return Result(
        symbol=symbol,
        value=value,
        unit=unit if unit is not None else base_unit(kind),
        kind=kind,
        formula=formula,
        substitutions=dict(substitutions),
        citation=citation,
        inputs_used=list(inputs_used),
        verdict=verdict,
        margin=margin,
        governing_case=governing_case,
        verification=verification,
        children=list(children) if children else [],
        issues=list(issues) if issues else [],
    )


def margin_verdict(available: float, required: float) -> tuple[Verdict, float]:
    """Compare an available quantity against a required one.

    Returns ``(verdict, margin)`` where ``margin`` is ``(available-required)/required``
    and PASS means available >= required.
    """
    if not math.isfinite(available) or not math.isfinite(required):
        raise ValueError(f"margin requires finite values, got available={available}, required={required}")
    if required <= 0:
        raise ValueError(f"required value must be > 0, got {required}")
    margin = (available - required) / required
    return (Verdict.PASS if margin >= 0 else Verdict.FAIL), margin


def require_positive(**values: float) -> None:
    """Raise for any non-positive, non-finite input (boundary check)."""
    for name, value in values.items():
        if math.isnan(value) or math.isinf(value):
            raise ValueError(f"{name} must be finite, got {value}")
        if value <= 0:
            raise ValueError(f"{name} must be > 0, got {value}")


def propagate_experimental_children(tree: ResultTree) -> None:
    """Make every descendant of an EXPERIMENTAL result EXPERIMENTAL (VAL-2).

    A result derived from provisional data must never render as ``verified``
    while its parent is honestly downgraded; only the subtree rooted at an
    EXPERIMENTAL result is propagated, so independently verified checks keep
    their status.
    """

    def walk(parent: Result) -> None:
        if parent.verification is VerificationStatus.EXPERIMENTAL:
            for child in parent.children:
                child.verification = VerificationStatus.EXPERIMENTAL
                walk(child)
        else:
            for child in parent.children:
                walk(child)

    for root in tree.roots:
        walk(root)
