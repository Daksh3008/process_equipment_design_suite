"""Main window: pack-driven input form with live results (GUI-1/2/3).

The form is generated from the selected pack's pydantic JSON schema, where every
field carries ``label``, ``unit``, ``help`` and ``clause`` metadata (IN-1). A
family selector switches the active pack without restarting (NFR-7): the pack is
resolved through :mod:`pemds.packs.registry`, so a new equipment family appears
here with no edits. Sliders drive live recalculation (IN-2) and problems are
shown as typed issues (GUI-3); reports and drawings are exported through the same
engines the CLI uses.
"""

from __future__ import annotations

import sys
import webbrowser
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..core.calc import CalcContext
from ..core.registry import EditionRegistry
from ..core.result import ResultTree, Verdict
from ..core.units import UnitSystem, display_unit, format_value, from_base
from ..data.materials import MaterialsDB
from ..packs.registry import families, get_pack_class
from ..preview3d.viewer import Preview3DWidget

_VERDICT_COLOR = {
    Verdict.PASS: QColor("#1a7f37"),
    Verdict.FAIL: QColor("#cf222e"),
    Verdict.WARN: QColor("#bc4c00"),
    Verdict.NA: QColor("#555555"),
}
_VERDICT_TEXT = {
    Verdict.PASS: "PASS",
    Verdict.FAIL: "FAIL",
    Verdict.WARN: "WARN",
    Verdict.NA: "-",
}

#: Human labels for the family selector; experimental packs are flagged here too.
_FAMILY_LABELS = {
    "pressure_vessel": "Pressure vessel",
    "piping": "Piping",
    "flange": "Flange / nozzle",
    "storage_tank": "Storage tank (experimental)",
}

_VESSEL_DEMO = {
    "tag": "V-101",
    "orientation": "vertical",
    "inside_diameter_mm": 2000.0,
    "tangent_to_tangent_mm": 4000.0,
    "material_key": "SA-516-70",
    "head_material_key": "SA-516-70",
    "head_type": "ellipsoidal",
    "design_pressure_mpa": 1.0,
    "design_temperature_c": 150.0,
    "corrosion_allowance_mm": 3.0,
    "mill_undertolerance_mm": 0.3,
    "joint_type": "1",
    "radiography": "full",
    "provided_shell_thickness_mm": 16.0,
    "provided_head_thickness_mm": 16.0,
    "support_type": "skirt",
    "support_height_mm": 1200.0,
    "nozzles": [
        {
            "tag": "N1",
            "outside_diameter_mm": 219.1,
            "provided_neck_thickness_mm": 8.18,
            "projection_mm": 300.0,
            "elevation_mm": 800.0,
            "service": "process inlet",
        },
        {
            "tag": "N2",
            "outside_diameter_mm": 168.3,
            "provided_neck_thickness_mm": 7.11,
            "projection_mm": 250.0,
            "elevation_mm": 1800.0,
            "service": "vapour outlet",
        },
    ],
}

#: A working example for every GUI family, so switching families always shows a result.
_DEMOS: dict[str, dict] = {
    "pressure_vessel": _VESSEL_DEMO,
    "piping": {
        "tag": "L-101",
        "outside_diameter_mm": 168.3,
        "design_pressure_mpa": 1.5,
        "design_temperature_c": 150.0,
        "material_key": "SA-106-B",
        "corrosion_allowance_mm": 1.0,
        "weld_joint_factor": 1.0,
        "y_factor": 0.4,
        "mill_tolerance_pct": 12.5,
        "provided_wall_thickness_mm": 7.11,
    },
    "flange": {
        "tag": "FL-101",
        "size": "2",
        "material_group": "1.1",
        "design_pressure_mpa": 2.0,
        "design_temperature_c": 100.0,
        "gasket_type": "spiral-wound",
        "facing": "raised_face",
    },
    "storage_tank": {
        "tag": "TK-101",
        "diameter_mm": 10000.0,
        "design_liquid_height_mm": 8000.0,
        "material_key": "SA-516-70",
        "specific_gravity": 1.0,
        "design_temperature_c": 60.0,
        "provided_shell_thickness_mm": 10.0,
        "plate_width_mm": 2400.0,
        "plate_length_mm": 6000.0,
    },
}

_REMOVED_GUI_FAMILIES = {"heat_exchanger", "column", "pump"}
_GUI_FAMILIES = [f for f in families() if f not in _REMOVED_GUI_FAMILIES]

_MATERIAL_FIELDS = {"material_key", "head_material_key", "casing_material_key"}
_UNIT_SYSTEMS = (UnitSystem.SI, UnitSystem.IMPERIAL, UnitSystem.MIXED)
_ARRAY_FIELDS: set[str] = set()  # Nozzle editors are declared per-family below.
_NOZZLE_ARRAY_FIELDS = {"nozzles"}


class _NozzleEditor(QWidget):
    """A compact table editor for the straight-nozzle schedule (v1.5).

    Straight nozzles only: tag, outside diameter, neck thickness, projection,
    elevation and service are editable. Azimuth (circumferential position, used
    by the 3D preview) is not part of the straight-nozzle data entry and keeps
    its model default of 0 degrees.
    """

    COLUMNS = ("Tag", "OD (mm)", "Neck (mm)", "Proj (mm)", "Elev (mm)", "Service")

    def __init__(self) -> None:
        super().__init__()
        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(list(self.COLUMNS))
        self.table.setMinimumHeight(150)
        add_button = QPushButton("Add nozzle")
        remove_button = QPushButton("Remove selected")
        add_button.clicked.connect(self.add_row)
        remove_button.clicked.connect(self.remove_selected)
        buttons = QHBoxLayout()
        buttons.addWidget(add_button)
        buttons.addWidget(remove_button)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)
        layout.addLayout(buttons)

    def add_row(self, values: dict | None = None) -> None:
        values = values or {}
        defaults = ("N1", "168.3", "7.11", "150", "500", "")
        row = self.table.rowCount()
        self.table.insertRow(row)
        keys = (
            "tag",
            "outside_diameter_mm",
            "provided_neck_thickness_mm",
            "projection_mm",
            "elevation_mm",
            "service",
        )
        for column, (key, fallback) in enumerate(zip(keys, defaults)):
            value = values.get(key, fallback)
            text = "" if value is None else str(value)
            self.table.setItem(row, column, QTableWidgetItem(text))

    def remove_selected(self) -> None:
        rows = sorted({index.row() for index in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)

    def set_rows(self, rows: list[dict]) -> None:
        self.table.setRowCount(0)
        for row in rows:
            self.add_row(row)

    def rows(self) -> list[dict]:
        entries: list[dict] = []
        for row in range(self.table.rowCount()):
            tag = _cell_text(self.table, row, 0)
            if not tag:
                continue
            entries.append(
                {
                    "tag": tag,
                    "outside_diameter_mm": _as_float(_cell_text(self.table, row, 1)),
                    "provided_neck_thickness_mm": _optional_float(_cell_text(self.table, row, 2)),
                    "projection_mm": _as_float(_cell_text(self.table, row, 3)),
                    "elevation_mm": _as_float(_cell_text(self.table, row, 4)),
                    "service": _cell_text(self.table, row, 5),
                }
            )
        return entries


def _cell_text(table: QTableWidget, row: int, column: int) -> str:
    item = table.item(row, column)
    return item.text().strip() if item is not None else ""


def _as_float(text: str) -> float | None:
    if not text:
        return None
    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"{text!r} is not a number") from exc


def _optional_float(text: str) -> float | None:
    return _as_float(text) if text else None


@dataclass
class _Field:
    """One editable input field and how to read it back."""

    name: str
    label: str
    unit: str
    widget: QWidget
    default: object = None
    optional: bool = False
    optional_check: QCheckBox | None = None

    def value(self) -> object:
        if (
            self.optional
            and self.optional_check is not None
            and not self.optional_check.isChecked()
            and not isinstance(self.widget, _NozzleEditor)
        ):
            return None
        if isinstance(self.widget, _NozzleEditor):
            return self.widget.rows()
        if isinstance(self.widget, QCheckBox):
            return self.widget.isChecked()
        if isinstance(self.widget, QDoubleSpinBox):
            return self.widget.value()
        if isinstance(self.widget, QLineEdit):
            return self.widget.text().strip()
        if isinstance(self.widget, QComboBox):
            return self.widget.currentText()
        raise TypeError(f"unhandled widget for field {self.name!r}")


class MainWindow(QMainWindow):
    """The PEMDS application window."""

    def __init__(self, ctx: CalcContext | None = None) -> None:
        super().__init__()
        self.setWindowTitle("PEMDS — Process Equipment Mechanical Design Suite (v1.5)")
        self.resize(1360, 840)

        registry = EditionRegistry.load_default()
        materials = MaterialsDB.load_default()
        self._ctx = ctx or CalcContext(
            editions=registry.editions(), materials=materials, unit_system=UnitSystem.SI
        )
        self._family = "pressure_vessel"
        self._pack = get_pack_class(self._family)()
        self._demo: dict = _DEMOS[self._family]
        self._fields: list[_Field] = []
        self._inputs: BaseModel | None = None
        self._tree: ResultTree | None = None
        self._system = UnitSystem.SI
        self._loading = False

        self._build_ui()
        self._build_form()
        self.set_demo_values()

    # -------------------------------------------------------------------- UI --
    def _build_ui(self) -> None:
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)

        # --- left: input form -------------------------------------------------
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        family_row = QHBoxLayout()
        family_row.addWidget(QLabel("Equipment:"))
        self._family_combo = QComboBox()
        for family in _GUI_FAMILIES:
            self._family_combo.addItem(_FAMILY_LABELS.get(family, family), family)
        self._family_combo.currentIndexChanged.connect(self._on_family_changed)
        family_row.addWidget(self._family_combo, 1)
        left_layout.addLayout(family_row)

        form_host = QScrollArea()
        form_host.setWidgetResizable(True)
        form_host.setMinimumWidth(460)
        form_container = QWidget()
        self._form_layout = QFormLayout(form_container)
        self._form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form_host.setWidget(form_container)
        left_layout.addWidget(form_host, 1)
        layout.addWidget(left, 1)

        # --- right: results + 3D preview --------------------------------------
        right = QWidget()
        right_layout = QVBoxLayout(right)
        results_tab = QWidget()
        results_layout = QVBoxLayout(results_tab)
        toolbar = QHBoxLayout()
        self._auto_check = QCheckBox("Live")
        self._auto_check.setChecked(True)
        calc_button = QPushButton("Calculate")
        calc_button.clicked.connect(self.recalculate)
        demo_button = QPushButton("Reset demo")
        demo_button.clicked.connect(self.set_demo_values)
        self._units_combo = QComboBox()
        for label in (UnitSystem.SI, UnitSystem.IMPERIAL, UnitSystem.MIXED):
            self._units_combo.addItem(label.value, label)
        self._units_combo.currentIndexChanged.connect(self._on_units_changed)
        report_button = QPushButton("Report (PDF)")
        report_button.clicked.connect(self.export_report)
        drawing_button = QPushButton("Drawing (DXF+PDF)")
        drawing_button.clicked.connect(self.export_drawing)
        open_button = QPushButton("Open report")
        open_button.clicked.connect(self.open_report)
        toolbar.addWidget(self._auto_check)
        toolbar.addWidget(calc_button)
        toolbar.addWidget(demo_button)
        toolbar.addWidget(QLabel("Units:"))
        toolbar.addWidget(self._units_combo)
        toolbar.addStretch(1)
        toolbar.addWidget(open_button)
        toolbar.addWidget(report_button)
        toolbar.addWidget(drawing_button)
        right_layout.addLayout(toolbar)

        self._summary = QLabel("No calculation yet.")
        self._summary.setWordWrap(True)
        results_layout.addWidget(self._summary)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #cf222e;")
        self._error_label.setWordWrap(True)
        results_layout.addWidget(self._error_label)

        self._results = QTreeWidget()
        self._results.setHeaderLabels(["Symbol", "Value", "Verdict", "Margin", "Status", "Clause"])
        self._results.setColumnWidth(0, 90)
        self._results.setColumnWidth(5, 220)
        results_layout.addWidget(self._results, 1)

        self._preview = Preview3DWidget()
        tabs = QTabWidget()
        tabs.addTab(results_tab, "Results")
        tabs.addTab(self._preview, "3D preview")
        right_layout.addWidget(tabs, 1)

        self.statusBar().showMessage("Ready")
        self.setCentralWidget(central)
        layout.addWidget(right, 3)

    def _on_family_changed(self) -> None:
        family = self._family_combo.currentData()
        if not family or family == self._family:
            return
        self._family = str(family)
        self._pack = get_pack_class(self._family)()
        self._demo = _DEMOS.get(self._family, {})
        self._inputs = None
        self._tree = None
        self._build_form()
        self.set_demo_values()

    def _on_units_changed(self) -> None:
        index = self._units_combo.currentIndex()
        if not 0 <= index < len(_UNIT_SYSTEMS):
            return
        self._system = _UNIT_SYSTEMS[index]
        if self._tree is not None:
            self._render()

    # ------------------------------------------------------------- form logic --
    def _build_form(self) -> None:
        while self._form_layout.rowCount() > 0:
            self._form_layout.removeRow(0)
        self._fields.clear()

        schema = self._pack.Input.model_json_schema()["properties"]
        material_keys = self._ctx.materials.keys()
        for name, prop in schema.items():
            label = str(prop.get("label", name))
            unit = str(prop.get("unit", ""))
            help_text = str(prop.get("help", ""))
            clause = str(prop.get("clause", ""))
            prop_type = prop.get("type")
            any_of = prop.get("anyOf")
            if prop_type == "array" and name not in _NOZZLE_ARRAY_FIELDS:
                # Complex list fields (load cases, connection/load schedules) are not yet
                # editable in the generated form; they fall back to their model default.
                continue
            is_number = prop_type == "number" or (
                isinstance(prop_type, list) and "number" in prop_type
            ) or (isinstance(any_of, list) and any(i.get("type") == "number" for i in any_of))
            optional = (
                isinstance(prop_type, list) and "null" in prop_type
            ) or (isinstance(any_of, list) and any(i.get("type") == "null" for i in any_of))
            default = prop.get("default")

            widget: QWidget
            check: QCheckBox | None = None

            if name in _NOZZLE_ARRAY_FIELDS:
                editor = _NozzleEditor()
                editor.setToolTip(f"{help_text} — {clause}")
                widget = editor
            elif name in _MATERIAL_FIELDS:
                combo = QComboBox()
                combo.setEditable(True)
                combo.addItems(material_keys)
                combo.setCurrentText(str(default) if default is not None else "")
                combo.setToolTip(f"{help_text} — {clause}")
                widget = combo
            elif prop_type == "boolean":
                toggle = QCheckBox()
                toggle.setChecked(bool(default))
                toggle.setToolTip(f"{help_text} — {clause}")
                widget = toggle
            elif is_number:
                spin = QDoubleSpinBox()
                spin.setRange(-1.0e9, 1.0e9)
                spin.setDecimals(4)
                spin.setToolTip(f"{help_text} — {clause}")
                if isinstance(default, (int, float)):
                    spin.setValue(float(default))
                widget = spin
            elif prop.get("enum"):
                combo = QComboBox()
                combo.addItems([str(v) for v in prop["enum"]])
                combo.setToolTip(f"{help_text} — {clause}")
                if default is not None:
                    combo.setCurrentText(str(default))
                widget = combo
            else:
                line = QLineEdit(str(default) if default is not None else "")
                line.setToolTip(f"{help_text} — {clause}")
                widget = line

            row_widget: QWidget = widget
            if optional and not isinstance(widget, _NozzleEditor):
                check = QCheckBox("specify")
                check.setChecked(default is not None)
                check.toggled.connect(lambda on, w=widget: w.setEnabled(on))
                widget.setEnabled(default is not None)
                row = QWidget()
                row_layout = QHBoxLayout(row)
                row_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.setSpacing(6)
                row_layout.addWidget(check)
                row_layout.addWidget(widget, 1)
                row_widget = row

            field = _Field(
                name=name,
                label=label,
                unit=unit,
                widget=widget,
                default=default,
                optional=optional,
                optional_check=check,
            )
            self._fields.append(field)
            label_text = label if not unit else f"{label} [{unit}]"
            self._form_layout.addRow(QLabel(label_text), row_widget)
            self._wire(field)

    def _wire(self, field: _Field) -> None:
        if isinstance(field.widget, _NozzleEditor):
            field.widget.table.itemChanged.connect(self._changed)
        elif isinstance(field.widget, QDoubleSpinBox):
            field.widget.valueChanged.connect(self._changed)
        elif isinstance(field.widget, QCheckBox):
            field.widget.toggled.connect(self._changed)
        elif isinstance(field.widget, QLineEdit):
            field.widget.textChanged.connect(self._changed)
        elif isinstance(field.widget, QComboBox):
            field.widget.currentTextChanged.connect(self._changed)

    def _changed(self, *_args: object) -> None:
        if self._loading or not self._auto_check.isChecked():
            return
        QTimer.singleShot(250, self.recalculate)

    # ----------------------------------------------------------- recalc/main --
    def set_demo_values(self) -> None:
        self._loading = True
        for field in self._fields:
            if isinstance(field.widget, _NozzleEditor):
                rows = self._demo.get(field.name, [])
                field.widget.set_rows(rows if isinstance(rows, list) else [])
                continue
            self._reset_field(field)
            if field.name not in self._demo:
                continue
            value = self._demo[field.name]
            if field.optional and field.optional_check is not None:
                provided = value is not None
                field.optional_check.setChecked(provided)
                field.widget.setEnabled(provided)
            if value is None:
                continue
            if isinstance(field.widget, QDoubleSpinBox):
                field.widget.setValue(float(value))
            elif isinstance(field.widget, QCheckBox):
                field.widget.setChecked(bool(value))
            elif isinstance(field.widget, QComboBox):
                field.widget.setCurrentText(str(value))
            elif isinstance(field.widget, QLineEdit):
                field.widget.setText(str(value))
        self._loading = False
        self.recalculate()

    def _reset_field(self, field: _Field) -> None:
        """Restore one field to the value its model declared (demo reset)."""
        default = field.default
        if isinstance(field.widget, QDoubleSpinBox):
            field.widget.setValue(float(default) if isinstance(default, (int, float)) else 0.0)
        elif isinstance(field.widget, QCheckBox):
            field.widget.setChecked(bool(default))
        elif isinstance(field.widget, QComboBox):
            field.widget.setCurrentText(str(default) if default is not None else "")
        elif isinstance(field.widget, QLineEdit):
            field.widget.setText("" if default is None else str(default))
        if field.optional and field.optional_check is not None:
            field.optional_check.setChecked(default is not None)
            field.widget.setEnabled(default is not None)

    def _collect(self) -> dict[str, object]:
        return {field.name: field.value() for field in self._fields}

    def _collect_inputs(self):
        try:
            # Dynamic kwargs from the widget map; pydantic validates them at the boundary.
            return self._pack.Input(**self._collect())  # type: ignore[attr-defined]  # pack models share the contract
        except Exception as exc:  # noqa: BLE001 - pydantic ValidationError at the UI boundary
            first = str(exc).splitlines()[0] if str(exc).splitlines() else str(exc)
            self._show_error(first)
            return None

    def recalculate(self) -> None:
        self._error_label.setText("")
        inputs = self._collect_inputs()
        if inputs is None:
            return
        issues = self._pack.validate(inputs)
        errors = [issue for issue in issues if issue.severity.value == "error"]
        if errors:
            self._show_error("; ".join(issue.message for issue in errors))
            return
        try:
            self._inputs = inputs
            self._tree = self._pack.calculate(inputs, self._ctx)
            self._render()
        except Exception as exc:  # noqa: BLE001 - UI boundary surfaces any failure
            self._show_error(str(exc))

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._results.clear()
        self._summary.setText("Calculation not run — fix the inputs shown in the error below.")

    def _render(self) -> None:
        tree = self._tree
        if tree is None:
            return
        self._results.clear()
        for root in tree.roots:
            self._add_item(None, root)
        overall = tree.overall_verdict()
        color = _VERDICT_COLOR[overall].name()
        governing = tree.governing_case or "-"
        self._summary.setText(
            f"Overall verdict: <b style='color:{color}'>{overall.value.upper()}</b>"
            f" &middot; Governing case: {governing} &middot; {self._pack_status()}"
        )
        self.statusBar().showMessage(f"Units: {self._system.value} · checks: {len(tree.flatten())}")
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        """Rebuild the 3D preview; a preview failure never blocks the results (3D-2)."""
        if self._family != "pressure_vessel":
            self._preview.clear(
                f"3D preview is available for pressure vessels in v1.5;\n"
                f"the {_FAMILY_LABELS.get(self._family, self._family)} family is shown as results."
            )
            return
        if self._inputs is None or self._tree is None:
            return
        try:
            self._preview.show_vessel(self._inputs, self._tree)
        except Exception as exc:  # noqa: BLE001 - preview must never break calculation
            self.statusBar().showMessage(f"3D preview unavailable: {exc}")

    def _pack_status(self) -> str:
        if self._inputs is None:
            return ""
        material = getattr(self._inputs, "material_key", "n/a")
        return f"Family: {self._family} · Material: {material}"

    def _add_item(self, parent: QTreeWidgetItem | None, result) -> QTreeWidgetItem:
        item = QTreeWidgetItem(parent or self._results.invisibleRootItem())
        item.setText(0, result.symbol)
        item.setText(1, self._display_value(result))
        item.setText(2, _VERDICT_TEXT[result.verdict])
        item.setText(3, "n/a" if result.margin is None else f"{result.margin:+.1%}")
        item.setText(4, result.verification.value)
        item.setText(5, result.citation.clause)
        item.setForeground(2, _VERDICT_COLOR[result.verdict])
        item.setToolTip(0, result.formula)
        for child in result.children:
            self._add_item(item, child)
        return item

    def _display_value(self, result) -> str:
        if result.value is None:
            return "-"
        if result.kind == "dimensionless":
            return f"{result.value:.4g}"
        shown = from_base(result.value, result.kind, self._system)
        unit = display_unit(result.kind, self._system)
        return format_value(shown, unit)

    # ---------------------------------------------------------------- export --
    def _output_dir(self) -> Path:
        if self._inputs is None:
            raise RuntimeError("run a calculation before exporting")
        tag = str(getattr(self._inputs, "tag", "item"))
        return Path("out") / tag

    def export_report(self) -> None:
        if self._inputs is None or self._tree is None:
            QMessageBox.warning(self, "Nothing to export", "Run a calculation first.")
            return
        try:
            from ..report.engine import render_pdf

            target = self._output_dir() / "report.pdf"
            render_pdf(
                project_name="PEMDS session",
                equipment_id=str(getattr(self._inputs, "tag", "item")),
                family=self._pack.family,
                inputs=self._inputs,
                tree=self._tree,
                path=target,
                system=self._system,
            )
            QMessageBox.information(self, "Exported", f"Report written to {target}")
        except Exception as exc:  # noqa: BLE001 - UI boundary
            QMessageBox.critical(self, "Export failed", str(exc))

    def export_drawing(self) -> None:
        if self._inputs is None or self._tree is None:
            QMessageBox.warning(self, "Nothing to export", "Run a calculation first.")
            return
        try:
            out_dir = self._output_dir()
            out_dir.mkdir(parents=True, exist_ok=True)
            if self._family == "pressure_vessel":
                from ..drawing.ga import vessel_ga_from
                from ..drawing.ga import write_dxf as ga_write_dxf
                from ..drawing.ga import write_pdf as ga_write_pdf

                ga = vessel_ga_from(self._inputs, self._tree, self._system)
                dxf = ga_write_dxf(ga, out_dir / "drawing.dxf")
                pdf = ga_write_pdf(ga, out_dir / "drawing.pdf")
            elif self._family == "pump":
                from ..packs.pu.drawing import pump_ga_from
                from ..packs.pu.drawing import write_dxf as pump_write_dxf
                from ..packs.pu.drawing import write_pdf as pump_write_pdf
                from ..packs.pu.model import PumpInputs

                if not isinstance(self._inputs, PumpInputs):
                    raise RuntimeError(
                        f"pump drawing requires PumpInputs, got {type(self._inputs).__name__}"
                    )
                ga = pump_ga_from(self._inputs, self._tree, self._system)
                dxf = pump_write_dxf(ga, out_dir / "drawing.dxf")
                pdf = pump_write_pdf(ga, out_dir / "drawing.pdf")
            else:
                QMessageBox.information(
                    self,
                    "No drawing",
                    f"A GA drawing is produced for pressure vessels and pumps in v1.5; "
                    f"the {self._family} family reports results only.",
                )
                return
            QMessageBox.information(self, "Exported", f"Drawing written to {dxf} and {pdf}")
        except Exception as exc:  # noqa: BLE001 - UI boundary
            QMessageBox.critical(self, "Export failed", str(exc))

    def open_report(self) -> None:
        if self._inputs is None or self._tree is None:
            QMessageBox.warning(self, "Nothing to export", "Run a calculation first.")
            return
        try:
            from ..report.engine import render_html

            target = self._output_dir() / "report.html"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                render_html(
                    project_name="PEMDS session",
                    equipment_id=str(getattr(self._inputs, "tag", "item")),
                    family=self._pack.family,
                    inputs=self._inputs,
                    tree=self._tree,
                    system=self._system,
                ),
                encoding="utf-8",
            )
            webbrowser.open(target.resolve().as_uri())
        except Exception as exc:  # noqa: BLE001 - UI boundary
            QMessageBox.critical(self, "Export failed", str(exc))


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover - interactive entry point
    sys.exit(main())
