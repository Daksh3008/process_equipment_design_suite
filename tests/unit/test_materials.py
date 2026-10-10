"""Material database tests (DB-1, DB-5)."""

from __future__ import annotations

import pytest

from pemds.data.materials import Material, MaterialsDB, StressPoint


def test_default_materials_load(materials: MaterialsDB):
    keys = materials.keys()
    assert "SA-516-70" in keys
    assert "SA-240-304" in keys


def test_allowable_stress_uses_next_higher_temperature(materials: MaterialsDB):
    steel = materials.get("SA-516-70")
    assert steel.allowable_stress_at(150.0) == pytest.approx(138.0e6)
    # 343 is the last tabulated point; 320 uses the same value.
    assert steel.allowable_stress_at(320.0) == pytest.approx(138.0e6)


def test_allowable_stress_above_range_raises(materials: MaterialsDB):
    steel = materials.get("SA-516-70")
    with pytest.raises(ValueError, match="outside the tabulated"):
        steel.allowable_stress_at(500.0)


def test_allowable_stress_below_range_raises(materials: MaterialsDB):
    steel = materials.get("SA-516-70")
    with pytest.raises(ValueError, match="outside the tabulated"):
        steel.allowable_stress_at(-100.0)


def test_nan_temperature_rejected(materials: MaterialsDB):
    steel = materials.get("SA-516-70")
    with pytest.raises(ValueError, match="must be finite"):
        steel.allowable_stress_at(float("nan"))


def test_unknown_material_raises(materials: MaterialsDB):
    with pytest.raises(KeyError, match="unknown material"):
        materials.get("NOPE")


def test_custom_material_is_flagged(materials: MaterialsDB):
    custom = Material(
        key="COMPANY-A",
        name="Company steel A",
        specification="COMPANY-A",
        group="company",
        allowables=(StressPoint(20.0, 120.0e6),),
        moduli=(),
        yield_strength_pa=250.0e6,
        tensile_strength_pa=450.0e6,
        density_kg_m3=7850.0,
        provenance=materials.provenance,
    )
    added = materials.add_custom(custom)
    assert added.custom is True
    assert materials.get("COMPANY-A").custom is True
    with pytest.raises(ValueError, match="already exists"):
        materials.add_custom(custom)


_IS_AND_CATEGORY_MATERIALS = [
    "IS-2002-Gr-1",
    "IS-2002-Gr-2A",
    "IS-2002-Gr-2B",
    "IS-2041-Gr-20Mo55",
    "IS-2041-Gr-20Mn2",
    "IS-1570-Gr-15Cr90Mo55",
    "IS-1570-Gr-C15Mn75",
    "HR-CARBON-STEEL",
    "5Cr-Mo-STEEL",
    "11.8Cr-Ni-STEEL",
    "13Cr-Ni-STEEL",
    "18Cr-2Ni-STEEL",
]


def test_requested_is_and_category_materials_are_present(materials: MaterialsDB):
    keys = set(materials.keys())
    for key in _IS_AND_CATEGORY_MATERIALS:
        assert key in keys, key


def test_requested_materials_resolve_allowable_stress(materials: MaterialsDB):
    for key in _IS_AND_CATEGORY_MATERIALS:
        material = materials.get(key)
        # Every added material resolves a positive allowable stress at 150 degC.
        assert material.allowable_stress_at(150.0) > 0.0
        assert material.density_kg_m3 > 0.0
        assert "UNVERIFIED" in material.provenance.checked_by.upper()
