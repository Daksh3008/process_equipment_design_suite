"""Provenance: the citation and verification metadata attached to every result.

Every calculated number carries ``{standard, edition, clause}`` (CIT-1) and a
verification status (VAL-2). Every transcribed data row carries the richer
:class:`Provenance` record required by the data policy (specification section 6).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class VerificationStatus(str, Enum):
    """Whether a check has been verified (VAL-2)."""

    VERIFIED = "verified"
    EXPERIMENTAL = "experimental"


@dataclass(frozen=True)
class Citation:
    """A reference to a clause of a standard.

    Only the reference is stored; normative prose is never reproduced.
    """

    standard: str
    edition: str
    clause: str
    source_tag: str | None = None

    def label(self) -> str:
        """Human-readable citation, e.g. ``ASME BPVC Section VIII, Division 1 (2023), UG-27(c)(1)``."""
        return f"{self.standard} ({self.edition}), {self.clause}"

    def to_dict(self) -> dict[str, str | None]:
        return {
            "standard": self.standard,
            "edition": self.edition,
            "clause": self.clause,
            "source_tag": self.source_tag,
        }


@dataclass(frozen=True)
class Provenance:
    """Provenance metadata for a transcribed data row or table."""

    source: str
    edition: str
    clause: str
    licence: str
    transcribed_on: str
    checked_by: str
    source_tag: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "source": self.source,
            "edition": self.edition,
            "clause": self.clause,
            "licence": self.licence,
            "transcribed_on": self.transcribed_on,
            "checked_by": self.checked_by,
            "source_tag": self.source_tag,
        }
