"""Fluid-material compatibility rule tests (CC-5)."""

from __future__ import annotations

from pemds.data.compatibility import compatibility_warnings, load_rules
from pemds.data.components import ComponentDB
from pemds.data.materials import MaterialsDB


def _messages(issues) -> str:
    return " ".join(i.message.casefold() for i in issues)


def test_chloride_service_flags_austenitic_stainless(editions):
    db = ComponentDB.load_default()
    material = MaterialsDB.load_default().get("SA-240-304")
    issues = compatibility_warnings(
        db.get("Water"), material, 80.0, editions, service="cooling water with chlorides"
    )
    assert "chloride" in _messages(issues)
    assert all(i.severity.value == "warning" for i in issues)  # warnings, never errors
    assert all(i.rationale for i in issues)


def test_carbon_steel_low_temperature_flags_brittle_fracture(editions):
    db = ComponentDB.load_default()
    material = MaterialsDB.load_default().get("SA-516-70")
    issues = compatibility_warnings(db.get("Benzene"), material, -50.0, editions)
    assert "brittle" in _messages(issues)


def test_water_service_flags_carbon_steel_corrosion(editions):
    db = ComponentDB.load_default()
    material = MaterialsDB.load_default().get("SA-516-70")
    issues = compatibility_warnings(db.get("Water"), material, 25.0, editions)
    assert "corros" in _messages(issues)


def test_compatible_pair_produces_no_warning(editions):
    db = ComponentDB.load_default()
    material = MaterialsDB.load_default().get("SA-240-304")
    issues = compatibility_warnings(db.get("Benzene"), material, 25.0, editions)
    assert issues == []


def test_rule_table_loads_with_rationale_and_source(editions):
    rules = load_rules()
    assert rules
    assert all(rule.source_tag for rule in rules)
    assert all(rule.rationale for rule in rules)
