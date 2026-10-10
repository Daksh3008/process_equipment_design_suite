"""Calculation context and the calc registry contract.

A calculation is a pure function of its inputs and the context. The context
carries the material database and the code editions in force; it performs no
I/O. Determinism (NFR-2) follows from calcs having no other inputs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from .provenance import Citation, VerificationStatus
from .result import Result
from .units import UnitSystem

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..data.materials import MaterialsDB


@dataclass(frozen=True)
class CodeEditions:
    """The edition in force for each standard (D1, DB-4)."""

    values: dict[str, str]

    def edition(self, standard: str) -> str:
        try:
            return self.values[standard]
        except KeyError as exc:
            raise KeyError(
                f"no edition configured for {standard!r}; configured: {sorted(self.values)}"
            ) from exc


@dataclass
class CalcContext:
    """Everything a calculation needs besides its explicit inputs."""

    editions: CodeEditions
    materials: MaterialsDB
    unit_system: UnitSystem = UnitSystem.SI


class Calc(Protocol):
    """Structural type for a calculation object."""

    id: str
    citation: Citation
    verification: VerificationStatus

    def __call__(self, inputs: object, ctx: CalcContext) -> Result: ...


@dataclass(frozen=True)
class CalcMeta:
    """Provenance metadata attached to a calculation function.

    The standard and clause are constants; the edition is resolved at run time
    from the registry so that DB-7 can switch editions without touching code.
    """

    standard: str
    clause: str
    source_tag: str
    verification: VerificationStatus = VerificationStatus.VERIFIED


def provable(
    standard: str,
    clause: str,
    source_tag: str,
    verification: VerificationStatus = VerificationStatus.VERIFIED,
):
    """Decorate a calculation function with its clause provenance (CIT-1/CIT-4)."""

    def decorate(func: Callable[..., Result]) -> Callable[..., Result]:
        func.__pemds_meta__ = CalcMeta(standard, clause, source_tag, verification)  # type: ignore[attr-defined]  # dynamic attribute used by meta_of/citation_for
        return func

    return decorate


def meta_of(func: Callable[..., Result]) -> CalcMeta:
    """Return the provenance metadata attached by :func:`provable`."""
    meta = getattr(func, "__pemds_meta__", None)
    if meta is None:
        raise LookupError(f"calculation {getattr(func, '__name__', func)!r} has no provenance metadata")
    return meta


def citation_of(
    standard: str,
    clause: str,
    editions: CodeEditions,
    source_tag: str | None = None,
) -> Citation:
    """Mint a :class:`Citation` with the edition currently in force."""
    return Citation(standard, editions.edition(standard), clause, source_tag)


def citation_for(func: Callable[..., Result], editions: CodeEditions) -> Citation:
    """Mint a citation for *func* from its attached metadata."""
    meta = meta_of(func)
    return Citation(meta.standard, editions.edition(meta.standard), meta.clause, meta.source_tag)


@dataclass(frozen=True)
class CalcSpec:
    """A named calculation with the metadata required by the citation lint."""

    id: str
    citation: Citation
    verification: VerificationStatus
    func: Callable[..., Result]

    def __call__(self, *args: object, **kwargs: object) -> Result:
        return self.func(*args, **kwargs)
