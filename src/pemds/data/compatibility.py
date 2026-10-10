"""Fluid-material compatibility screening — FR-CC (CC-5).

Rule-based warnings when a selected body material meets a fluid it is known to
attack. Every rule is a heuristic with its own rationale and source tag; results
are **warnings only, never hard errors** (CC-5). The rules live in a
provenance-stamped data file and are matched against the component's identity
strings, an optional free-text service description, and the material group.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.calc import CodeEditions
from ..core.provenance import Citation
from ..core.result import Issue, Severity
from ..core.standards import ASME_VIII_1, NACE_MR0175
from .components import Component
from .loader import load_package_data
from .materials import Material

#: Rules reference a source tag; map it to the standard named in the citation.
_STANDARD_BY_TAG = {"S14": NACE_MR0175, "S1": ASME_VIII_1}


@dataclass(frozen=True)
class CompatibilityRule:
    """One fluid-material screening rule."""

    id: str
    fluid_keywords: tuple[str, ...]
    material_groups: tuple[str, ...]
    message: str
    rationale: str
    source_tag: str
    min_temperature_c: float | None = None
    temperature_below_c: float | None = None


def load_rules() -> list[CompatibilityRule]:
    """Load the compatibility rule table from package data."""
    data_file = load_package_data("components/compatibility_rules.json")
    rules: list[CompatibilityRule] = []
    for raw in data_file.data.get("rules", []):
        rules.append(
            CompatibilityRule(
                id=str(raw["id"]),
                fluid_keywords=tuple(str(k).casefold() for k in raw.get("fluid_keywords", [])),
                material_groups=tuple(str(g).casefold() for g in raw.get("material_groups", [])),
                message=str(raw["message"]),
                rationale=str(raw["rationale"]),
                source_tag=str(raw["source_tag"]),
                min_temperature_c=(
                    float(raw["min_temperature_c"]) if raw.get("min_temperature_c") is not None else None
                ),
                temperature_below_c=(
                    float(raw["temperature_below_c"])
                    if raw.get("temperature_below_c") is not None
                    else None
                ),
            )
        )
    if not rules:
        raise ValueError("components/compatibility_rules.json contains no rules")
    return rules


def _fluid_matches(rule: CompatibilityRule, component: Component, service: str) -> bool:
    if not rule.fluid_keywords:
        return True  # fluid-agnostic rule (e.g. a temperature limit)
    haystack = " ".join((*component.searchable(), service.casefold()))
    return any(keyword in haystack for keyword in rule.fluid_keywords)


def _material_matches(rule: CompatibilityRule, material: Material) -> bool:
    if not rule.material_groups:
        return True
    haystack = f"{material.group.casefold()} {material.name.casefold()} {material.specification.casefold()}"
    return any(group in haystack for group in rule.material_groups)


def _temperature_matches(rule: CompatibilityRule, temperature_c: float) -> bool:
    return not (
        (rule.min_temperature_c is not None and temperature_c < rule.min_temperature_c)
        or (rule.temperature_below_c is not None and temperature_c >= rule.temperature_below_c)
    )


def compatibility_warnings(
    component: Component,
    material: Material,
    temperature_c: float,
    editions: CodeEditions,
    service: str = "",
) -> list[Issue]:
    """Return the compatibility warnings for *component* against *material* (CC-5)."""
    issues: list[Issue] = []
    for rule in load_rules():
        if (
            _fluid_matches(rule, component, service)
            and _material_matches(rule, material)
            and _temperature_matches(rule, temperature_c)
        ):
            standard = _STANDARD_BY_TAG.get(rule.source_tag)
            citation = (
                Citation(standard, editions.edition(standard), "compatibility screening", rule.source_tag)
                if standard
                else None
            )
            issues.append(
                Issue(
                    severity=Severity.WARNING,
                    message=rule.message,
                    field="material_key",
                    rationale=rule.rationale,
                    citation=citation,
                )
            )
    return issues
