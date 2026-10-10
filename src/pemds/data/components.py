"""Chemical component identity database — FR-CC (CC-1, CC-10).

The identity rows (name, synonyms, CAS, formula, molar mass) are a static
snapshot generated from the pinned CoolProp release (see
``scripts/generate_component_identity.py``); CoolProp builds them from the NIST
Chemistry WebBook and REFPROP. Loading this file needs no third-party runtime,
so the application stays offline-first (NFR-8); CoolProp is required only for
property *evaluation* (:mod:`pemds.data.fluid_properties`).

Every row carries provenance; the snapshot is flagged ``UNVERIFIED`` in
``checked_by`` because it has not been independently reviewed row by row, and
callers must not present it as a verified design input (CC-10, VAL-2).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from ..core.provenance import Provenance
from .loader import load_package_data


@dataclass(frozen=True)
class Component:
    """One chemical component identity record."""

    key: str
    name: str
    cas: str
    formula: str
    aliases: tuple[str, ...]
    molar_mass_kg_mol: float
    provenance: Provenance

    def searchable(self) -> tuple[str, ...]:
        """All casefolded strings a search query may match."""
        terms = [self.key, self.name, self.cas, self.formula]
        terms.extend(self.aliases)
        return tuple(term.casefold() for term in terms if term)


class ComponentDB:
    """A queryable collection of component identity records."""

    def __init__(self, components: dict[str, Component], provenance: Provenance) -> None:
        self._components = dict(components)
        self.provenance = provenance

    @classmethod
    def load_default(cls) -> ComponentDB:
        data_file = load_package_data("components/identities.json")
        components: dict[str, Component] = {}
        for raw in data_file.data.get("components", []):
            component = _component_from_json(raw, data_file.provenance)
            if component.key in components:
                raise ValueError(f"duplicate component key {component.key!r}")
            components[component.key] = component
        if not components:
            raise ValueError("components/identities.json contains no components")
        return cls(components, data_file.provenance)

    def get(self, key: str) -> Component:
        try:
            return self._components[key]
        except KeyError as exc:
            raise KeyError(
                f"unknown component {key!r}; use ComponentDB.search() or keys() to find one"
            ) from exc

    def keys(self) -> list[str]:
        return sorted(self._components)

    def all(self) -> list[Component]:
        return [self._components[k] for k in self.keys()]

    def search(self, query: str) -> list[Component]:
        """Components whose name/key/CAS/formula/alias contains *query* (case-insensitive)."""
        needle = query.strip().casefold()
        if not needle:
            return []
        return [c for c in self.all() if any(needle in term for term in c.searchable())]


@lru_cache(maxsize=1)
def default_components() -> ComponentDB:
    """Process-wide default component database, loaded once (CC-1)."""
    return ComponentDB.load_default()


def _component_from_json(raw: dict, provenance: Provenance) -> Component:
    try:
        return Component(
            key=str(raw["key"]),
            name=str(raw["name"]),
            cas=str(raw.get("cas", "")),
            formula=str(raw.get("formula", "")),
            aliases=tuple(str(a) for a in raw.get("aliases", [])),
            molar_mass_kg_mol=float(raw["molar_mass_kg_mol"]),
            provenance=provenance,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid component record {raw.get('key', raw)!r}: {exc}") from exc
