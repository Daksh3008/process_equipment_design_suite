"""Validation: distinguishes hard errors from warnings (IN-4).

Inputs are validated at the boundary (the pack), not inside calculations.
An error blocks calculation; a warning does not. Every issue can name the field
it belongs to so the GUI can jump to it (GUI-3).
"""

from __future__ import annotations

from .provenance import Citation
from .result import Issue, Severity


class ValidationError(Exception):
    """Raised when a validation pass found at least one hard error."""

    def __init__(self, issues: list[Issue]) -> None:
        self.issues = list(issues)
        summary = "; ".join(i.message for i in self.issues if i.severity is Severity.ERROR)
        super().__init__(summary or "validation failed")


class IssueCollector:
    """Accumulates typed issues during validation."""

    def __init__(self) -> None:
        self._issues: list[Issue] = []

    def error(
        self,
        message: str,
        field: str | None = None,
        rationale: str | None = None,
        citation: Citation | None = None,
    ) -> None:
        self._issues.append(Issue(Severity.ERROR, message, field, rationale, citation))

    def warning(
        self,
        message: str,
        field: str | None = None,
        rationale: str | None = None,
        citation: Citation | None = None,
    ) -> None:
        self._issues.append(Issue(Severity.WARNING, message, field, rationale, citation))

    @property
    def issues(self) -> list[Issue]:
        return list(self._issues)

    @property
    def has_errors(self) -> bool:
        return any(i.severity is Severity.ERROR for i in self._issues)

    def raise_if_errors(self) -> None:
        if self.has_errors:
            raise ValidationError(self._issues)
