"""Component identity database tests (CC-1, CC-10)."""

from __future__ import annotations

import pytest

from pemds.data.components import ComponentDB, default_components


def test_database_has_the_promised_breadth():
    db = ComponentDB.load_default()
    # CC-1 requires ~100+ common process chemicals.
    assert len(db.keys()) >= 100


def test_search_by_name_cas_and_alias():
    db = ComponentDB.load_default()
    assert db.get("Water").cas == "7732-18-5"
    assert "Water" in [c.key for c in db.search("water")]
    assert "Water" in [c.key for c in db.search("7732-18-5")]  # CAS search
    assert "Water" in [c.key for c in db.search("R718")]  # refrigerant alias search
    assert "Water" in [c.key for c in db.search("H2O")]  # formula search


def test_identity_row_is_complete():
    water = ComponentDB.load_default().get("Water")
    assert water.name == "Water"
    assert water.formula == "H2O"
    assert water.molar_mass_kg_mol == pytest.approx(0.018015, rel=1e-4)
    assert water.provenance.checked_by  # provenance is present (CC-10)


def test_unknown_component_fails_loudly():
    with pytest.raises(KeyError):
        ComponentDB.load_default().get("Unobtainium")


def test_empty_query_returns_nothing():
    assert ComponentDB.load_default().search("") == []


def test_default_components_is_cached():
    assert default_components() is default_components()
