"""GUI family switching across the v1.5 packs (GUI-1/2, NFR-7)."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from pemds.gui.main import MainWindow

APPLICATION = QApplication.instance() or QApplication([])


def _window() -> MainWindow:
    window = MainWindow()
    window.show()
    return window


def test_default_family_is_the_pressure_vessel():
    window = _window()
    assert window._family == "pressure_vessel"
    assert window._tree is not None and window._tree.overall_verdict().value == "pass"


def test_family_selector_excludes_removed_packs():
    window = _window()
    offered = {window._family_combo.itemData(i) for i in range(window._family_combo.count())}
    assert offered == {"pressure_vessel", "piping", "flange", "storage_tank"}
    assert offered.isdisjoint({"heat_exchanger", "column", "pump"})


def test_switch_to_flange_rebuilds_form_and_calculates():
    window = _window()
    window._family_combo.setCurrentText("Flange / nozzle")
    assert window._family == "flange"
    assert window._tree is not None
    assert any(field.name == "size" for field in window._fields)
    assert not any(field.name == "inside_diameter_mm" for field in window._fields)
    # Gasket type and facing are closed dropdowns (v1.5).
    gasket = next(field for field in window._fields if field.name == "gasket_type")
    assert gasket.widget.count() == 3


def test_experimental_family_is_badged_in_the_status_column():
    window = _window()
    window._family_combo.setCurrentText("Storage tank (experimental)")
    assert window._family == "storage_tank"
    statuses = [
        window._results.topLevelItem(index).text(4)
        for index in range(window._results.topLevelItemCount())
    ]
    assert "experimental" in statuses


def test_storage_tank_exposes_plate_dimensions():
    window = _window()
    window._family_combo.setCurrentText("Storage tank (experimental)")
    names = {field.name for field in window._fields}
    assert {"plate_width_mm", "plate_length_mm", "include_roof_calculation"} <= names


def _material_combo(window):
    return next(field.widget for field in window._fields if field.name == "material_key")


def test_requested_materials_are_offered_for_every_gui_equipment():
    window = _window()
    for label in ("Pressure vessel", "Piping", "Storage tank (experimental)"):
        window._family_combo.setCurrentText(label)
        combo = _material_combo(window)
        offered = {combo.itemText(i) for i in range(combo.count())}
        assert "IS-2002-Gr-2A" in offered, label
        assert "IS-1570-Gr-15Cr90Mo55" in offered, label
        assert "HR-CARBON-STEEL" in offered, label