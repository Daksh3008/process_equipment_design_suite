"""Edition registry (DB-4, DB-7 foundation).

Resolves which edition of each standard is in force and mints citations from it,
so no calculation hard-codes an edition string.
"""

from __future__ import annotations

from .calc import CodeEditions
from .provenance import Citation


class EditionRegistry:
    """Maps standard name -> edition and produces citations."""

    def __init__(self, values: dict[str, str]) -> None:
        if not values:
            raise ValueError("edition registry requires at least one standard")
        self._values = dict(values)

    @classmethod
    def load_default(cls) -> EditionRegistry:
        from ..data.loader import load_data_file

        data_file = load_data_file("codes/editions.json")
        editions = data_file.data.get("editions")
        if not isinstance(editions, dict) or not editions:
            raise ValueError("codes/editions.json must contain a non-empty 'editions' object")
        return cls({str(k): str(v) for k, v in editions.items()})

    def editions(self) -> CodeEditions:
        return CodeEditions(dict(self._values))

    def citation(self, standard: str, clause: str, source_tag: str | None = None) -> Citation:
        return Citation(standard, self._values[standard], clause, source_tag)
