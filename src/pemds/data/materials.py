"""Material database (DB-1, DB-5).

Allowable stress and elastic modulus are functions of temperature. Design values
are read conservatively: the value at the next-higher tabulated temperature is
used, never an interpolated value. Custom records (DB-5) are flagged and carried
into reports.
"""

from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass, replace
from itertools import pairwise

from ..core.provenance import Provenance
from .loader import load_package_data

_MPa = 1.0e6
_GPa = 1.0e9


@dataclass(frozen=True)
class StressPoint:
    temperature_c: float
    allowable_stress_pa: float


@dataclass(frozen=True)
class ModulusPoint:
    temperature_c: float
    modulus_pa: float


@dataclass(frozen=True)
class Material:
    """One material with temperature-dependent design values."""

    key: str
    name: str
    specification: str
    group: str
    allowables: tuple[StressPoint, ...]
    moduli: tuple[ModulusPoint, ...]
    yield_strength_pa: float
    tensile_strength_pa: float
    density_kg_m3: float
    provenance: Provenance
    custom: bool = False

    def _step_lookup(self, points, temperature_c: float, value_of, label: str) -> float:
        if not points:
            raise ValueError(f"{self.key}: no {label} data available")
        if not math.isfinite(temperature_c):
            raise ValueError(f"{self.key}: temperature must be finite, got {temperature_c}")
        temps = [p.temperature_c for p in points]
        if temperature_c < temps[0] or temperature_c > temps[-1]:
            raise ValueError(
                f"{self.key}: temperature {temperature_c:g} degC is outside the tabulated "
                f"{label} range ({temps[0]:g} to {temps[-1]:g} degC)"
            )
        idx = bisect_left(temps, temperature_c)
        return value_of(points[idx])

    def allowable_stress_at(self, temperature_c: float) -> float:
        """Allowable stress in Pa at *temperature_c*, using the next-higher table value."""
        return self._step_lookup(
            self.allowables, temperature_c, lambda p: p.allowable_stress_pa, "allowable stress"
        )

    def modulus_at(self, temperature_c: float) -> float:
        """Elastic modulus in Pa at *temperature_c*, using the next-higher table value."""
        return self._step_lookup(self.moduli, temperature_c, lambda p: p.modulus_pa, "modulus")


class MaterialsDB:
    """A queryable collection of materials."""

    def __init__(self, materials: dict[str, Material], provenance: Provenance) -> None:
        self._materials = dict(materials)
        self.provenance = provenance

    @classmethod
    def load_default(cls) -> MaterialsDB:
        data_file = load_package_data("materials/materials_asme_ii_d.json")
        materials: dict[str, Material] = {}
        for raw in data_file.data.get("materials", []):
            material = _material_from_json(raw, data_file.provenance)
            if material.key in materials:
                raise ValueError(f"duplicate material key {material.key!r}")
            materials[material.key] = material
        if not materials:
            raise ValueError("materials data file contains no materials")
        return cls(materials, data_file.provenance)

    def get(self, key: str) -> Material:
        try:
            return self._materials[key]
        except KeyError as exc:
            raise KeyError(f"unknown material {key!r}; available: {sorted(self._materials)}") from exc

    def keys(self) -> list[str]:
        return sorted(self._materials)

    def all(self) -> list[Material]:
        return [self._materials[k] for k in self.keys()]

    def add_custom(self, material: Material) -> Material:
        """Add a user material (DB-5); it is flagged ``custom`` and shown in reports."""
        if material.key in self._materials:
            raise ValueError(f"material key {material.key!r} already exists")
        custom = replace(material, custom=True)
        self._materials[custom.key] = custom
        return custom


def _require_ascending(points, label: str, key: str) -> None:
    temps = [p.temperature_c for p in points]
    if any(not math.isfinite(t) for t in temps):
        raise ValueError(f"{key}: {label} contains a non-finite temperature: {temps}")
    if any(b <= a for a, b in pairwise(temps)):
        raise ValueError(f"{key}: {label} temperatures must be strictly ascending, got {temps}")


def _require_finite_positive(values, label: str, key: str) -> None:
    for value in values:
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{key}: {label} values must be finite and > 0, got {value}")


def _material_from_json(raw: dict, provenance: Provenance) -> Material:
    try:
        allowables = tuple(
            StressPoint(float(t), float(s) * _MPa) for t, s in raw["allowable_stress_MPa"]
        )
        moduli = tuple(
            ModulusPoint(float(t), float(e) * _GPa) for t, e in (raw.get("modulus_GPa") or [])
        )
        _require_ascending(allowables, "allowable_stress_MPa", raw["key"])
        _require_ascending(moduli, "modulus_GPa", raw["key"])
        _require_finite_positive(
            (p.allowable_stress_pa for p in allowables), "allowable_stress_MPa", raw["key"]
        )
        _require_finite_positive((p.modulus_pa for p in moduli), "modulus_GPa", raw["key"])
        return Material(
            key=str(raw["key"]),
            name=str(raw["name"]),
            specification=str(raw["specification"]),
            group=str(raw["group"]),
            allowables=allowables,
            moduli=moduli,
            yield_strength_pa=float(raw["yield_MPa"]) * _MPa,
            tensile_strength_pa=float(raw["tensile_MPa"]) * _MPa,
            density_kg_m3=float(raw["density_kg_m3"]),
            provenance=provenance,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid material record {raw.get('key', raw)!r}: {exc}") from exc
