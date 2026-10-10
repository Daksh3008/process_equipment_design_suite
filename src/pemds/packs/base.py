"""The pack protocol.

A pack owns one equipment family: its input model, its validation, and the
orchestration of the shared calculation modules into a :class:`ResultTree`. The
output engines (drawing, report, 3D) are injected as separate objects so the
calculation path stays free of I/O and heavy rendering dependencies.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from ..core.calc import CalcContext
from ..core.result import Issue, ResultTree


@runtime_checkable
class Pack(Protocol):
    """Structural type for an equipment pack."""

    family: str
    Input: type[BaseModel]

    def validate(self, inputs: BaseModel) -> list[Issue]:
        """Return issues for *inputs*; error issues block calculation."""
        ...

    def calculate(self, inputs: BaseModel, ctx: CalcContext) -> ResultTree:
        """Run the pack's calculations and return the result tree."""
        ...
