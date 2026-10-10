"""Headless GUI tests (GUI-1/2/3) — run with the offscreen Qt platform."""

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


def test_demo_calculates_on_open():
    window = _window()
    assert window._tree is not None
    assert window._tree.overall_verdict().value == "pass"


def test_live_recalc_responds_to_slider():
    window = _window()
    pressure = next(field for field in window._fields if field.name == "design_pressure_mpa")
    pressure.widget.setValue(3.0)
    window.recalculate()
    assert window._tree is not None
    assert window._tree.overall_verdict().value == "fail"
    assert any(issue.severity.value == "warning" for issue in window._tree.all_issues())


def test_invalid_input_is_reported_not_crashed():
    window = _window()
    thickness = next(
        field for field in window._fields if field.name == "provided_shell_thickness_mm"
    )
    thickness.widget.setValue(3.0)  # below CA + mill tolerance -> validation error
    window.recalculate()
    assert "thickness" in window._error_label.text().lower()


def test_screenshot_is_captured(tmp_path):
    window = _window()
    shot = tmp_path / "pemds-gui.png"
    ok = window.grab().save(str(shot))
    assert ok and shot.is_file() and shot.stat().st_size > 1000


def test_units_toggle_rerenders():
    window = _window()
    window._units_combo.setCurrentIndex(1)  # IMPERIAL is the second entry
    assert window._system.value == "IMPERIAL"
    values = [
        window._results.topLevelItem(index).text(1)
        for index in range(window._results.topLevelItemCount())
    ]
    assert any(value.endswith("psi") for value in values)  # pressures in psi
    assert any(value.endswith("in") for value in values)  # lengths in inches


def test_3d_tab_and_nozzle_editor_are_present():
    window = _window()
    assert window._preview is not None
    editor = next(field.widget for field in window._fields if field.name == "nozzles")
    assert len(editor.rows()) == 2  # the demo vessel ships two nozzles


def test_adding_a_nozzle_recalculates_it():
    window = _window()
    editor = next(field.widget for field in window._fields if field.name == "nozzles")
    editor.add_row(
        {
            "tag": "N9",
            "outside_diameter_mm": 273.0,
            "provided_neck_thickness_mm": 9.27,
            "projection_mm": 200.0,
            "elevation_mm": 3000.0,
            "azimuth_deg": 270.0,
            "service": "drain",
        }
    )
    window.recalculate()
    assert any(result.symbol == "nozzle_N9" for result in window._tree.roots)


def test_preview_regenerates_on_recalculate():
    window = _window()
    assert len(window._preview._figure.axes) == 1
    window.recalculate()
    assert len(window._preview._figure.axes) == 1