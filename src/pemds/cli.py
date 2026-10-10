"""Command-line interface (headless run of a project).

Usage::

    pemds calc project.json --out out/
    pemds version

For each pressure-vessel item the CLI writes ``results.json``, ``report.html``,
``report.pdf``, a GA drawing (``drawing.dxf``, ``drawing.pdf``) and a 3D preview
(``preview.png``, ``preview.stl``).
"""

from __future__ import annotations

import argparse
import csv
import datetime as _dt
import html
import io
import json
import re
import shutil
import sys
from pathlib import Path

from . import __version__
from .core.calc import CalcContext
from .core.registry import EditionRegistry
from .core.units import UnitSystem
from .core.validation import ValidationError
from .data.loader import DataError
from .data.materials import MaterialsDB
from .persistence.store import ProjectError, ProjectStore

_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]+$")
_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def _get_pack(family: str):
    from .packs.registry import get_pack_class

    return get_pack_class(family)


def _load_inputs(family: str, raw: dict):
    return _get_pack(family).Input.model_validate(raw)


def _calculate(family: str, inputs, ctx: CalcContext):
    return _get_pack(family)().calculate(inputs, ctx)


def _safe_id(item_id: str) -> str:
    """Validate that an equipment id is a safe, portable output directory name."""
    if not _SAFE_ID.fullmatch(item_id):
        raise ValueError(
            f"equipment id {item_id!r} must contain only letters, digits, '.', '_' or '-'"
        )
    if item_id.startswith(".") or item_id.endswith(".") or ".." in item_id:
        raise ValueError(f"equipment id {item_id!r} must not start/end with '.' or contain '..'")
    if item_id.split(".")[0].upper() in _RESERVED_NAMES:
        raise ValueError(f"equipment id {item_id!r} is a reserved device name")
    if item_id.casefold().endswith(".staging"):
        raise ValueError(f"equipment id {item_id!r} ends with the reserved '.staging' suffix")
    if len(item_id) > 100:
        raise ValueError(f"equipment id is too long ({len(item_id)} characters; max 100)")
    return item_id


def _write_text_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()


def run_calc(project_path: Path, out_dir: Path, unit_system: str) -> int:
    try:
        system = UnitSystem(unit_system)
        project = ProjectStore(project_path).load()
        editions = EditionRegistry.load_default()
        materials = MaterialsDB.load_default()
        safe_ids = [_safe_id(item.id) for item in project.equipment]
    except (ProjectError, DataError, ValidationError, ValueError, KeyError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    folded = [item_id.casefold() for item_id in safe_ids]
    duplicates = sorted({item_id for item_id in folded if folded.count(item_id) > 1})
    if duplicates:
        print(f"error: duplicate equipment ids: {duplicates}", file=sys.stderr)
        return 1

    ctx = CalcContext(editions=editions.editions(), materials=materials, unit_system=system)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"error: cannot create output directory {out_dir}: {exc}", file=sys.stderr)
        return 1
    written: list[str] = []
    date = _dt.datetime.now(tz=_dt.UTC).date().isoformat()

    for item, item_id in zip(project.equipment, safe_ids):
        final_dir = out_dir / item_id
        staging = out_dir / f"{item_id}.staging"
        try:
            inputs = _load_inputs(item.family, item.inputs)
            tree = _calculate(item.family, inputs, ctx)
            if staging.exists():
                shutil.rmtree(staging)
            staging.mkdir(parents=True)
            produced = ["results.json"]
            _write_text_atomic(staging / "results.json", json.dumps(tree.to_dict(), indent=2))
            produced.extend(_write_equipment_outputs(item, project, inputs, tree, staging, system, date))
            # Swap the complete item directory into place only after every file exists.
            if final_dir.exists():
                shutil.rmtree(final_dir)
            staging.replace(final_dir)
            written.extend(str(final_dir / name) for name in produced)
        except (ValueError, KeyError, OSError, ValidationError, DataError) as exc:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
            print(f"error: {item.id}: {exc}", file=sys.stderr)
            return 1

    for path in written:
        print(path)
    return 0


def _write_equipment_outputs(item, project, inputs, tree, item_dir, system, date) -> list[str]:
    """Write the report set for any family; add drawings for the vessel pack."""
    from .report.engine import render_csv, render_html, render_pdf

    html = render_html(
        project_name=project.name,
        equipment_id=item.id,
        family=item.family,
        inputs=inputs,
        tree=tree,
        system=system,
    )
    _write_text_atomic(item_dir / "report.html", html)
    render_pdf(
        project_name=project.name,
        equipment_id=item.id,
        family=item.family,
        inputs=inputs,
        tree=tree,
        path=item_dir / "report.pdf",
        system=system,
    )
    _write_text_atomic(item_dir / "results.csv", render_csv(tree, system))
    names = ["report.html", "report.pdf", "results.csv"]
    if item.family == "pressure_vessel":
        from .drawing.ga import vessel_ga_from
        from .drawing.ga import write_dxf as write_ga_dxf
        from .drawing.ga import write_pdf as write_ga_pdf
        from .preview3d.export import write_stl
        from .preview3d.render import render_png
        from .preview3d.scene import vessel_scene_from

        ga = vessel_ga_from(inputs, tree, system)
        write_ga_dxf(
            ga, item_dir / "drawing.dxf", project=project.name, drawing_no=f"{item.id}-GA", date=date
        )
        write_ga_pdf(
            ga, item_dir / "drawing.pdf", project=project.name, drawing_no=f"{item.id}-GA", date=date
        )
        names += ["drawing.dxf", "drawing.pdf"]
        scene = vessel_scene_from(inputs, tree)
        render_png(scene, item_dir / "preview.png", title=f"{item.id} — 3D preview")
        write_stl(scene, item_dir / "preview.stl")
        names += ["preview.png", "preview.stl"]
    elif item.family == "pump":
        from .packs.pu.drawing import pump_ga_from
        from .packs.pu.drawing import write_dxf as write_pump_dxf
        from .packs.pu.drawing import write_pdf as write_pump_pdf

        ga = pump_ga_from(inputs, tree, system)
        write_pump_dxf(ga, item_dir / "drawing.dxf")
        write_pump_pdf(ga, item_dir / "drawing.pdf")
        names += ["drawing.dxf", "drawing.pdf"]
        names += _write_pump_datasheet(item_dir, inputs, tree, system)
    return names


def _write_pump_datasheet(item_dir: Path, inputs, tree, system) -> list[str]:
    """API 610-style pump datasheet as CSV and PDF (PU-14)."""
    from .packs.pu.datasheet import pump_datasheet_rows

    rows = pump_datasheet_rows(inputs, tree)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["Field", "Value"])
    writer.writerows([[name, value] for name, value in rows])
    _write_text_atomic(item_dir / "datasheet.csv", buffer.getvalue())

    from reportlab.lib import (
        colors,
    )
    from reportlab.lib.pagesizes import (
        A4,
    )
    from reportlab.lib.styles import (
        getSampleStyleSheet,
    )
    from reportlab.lib.units import (
        mm,
    )
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Table,
        TableStyle,
    )

    styles = getSampleStyleSheet()
    table_data = [["Field", "Value"]] + [
        [html.escape(name), html.escape(str(value))] for name, value in rows
    ]
    table = Table(table_data, colWidths=[75 * mm, 115 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    doc = SimpleDocTemplate(str(item_dir / "datasheet.pdf"), pagesize=A4, title="Pump datasheet")
    doc.build(
        [
            Paragraph("Pump datasheet (API 610 style)", styles["Title"]),
            Paragraph(f"Unit system: {system.value}", styles["Normal"]),
            table,
        ]
    )
    return ["datasheet.csv", "datasheet.pdf"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pemds", description="Process Equipment Mechanical Design Suite")
    parser.add_argument("--version", action="version", version=f"pemds {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    calc = sub.add_parser("calc", help="run calculations for a project file")
    calc.add_argument("project", type=Path, help="path to the project JSON")
    calc.add_argument("--out", type=Path, default=Path("out"), help="output directory")
    calc.add_argument(
        "--units",
        choices=["SI", "IMPERIAL", "MIXED"],
        default="SI",
        help="display unit system",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "calc":
        return run_calc(args.project, args.out, args.units)
    parser.error(f"unknown command {args.command!r}")  # pragma: no cover - argparse guards
    return 2


if __name__ == "__main__":  # pragma: no cover - module entry point
    sys.exit(main())
