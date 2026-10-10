"""End-to-end CLI coverage for every v1.0 equipment family (NFR-7, EXT-1)."""

from __future__ import annotations

import json
from pathlib import Path

from pemds.cli import main
from pemds.packs.registry import families, get_pack_class

ROOT = Path(__file__).resolve().parents[1]
ALL_FAMILIES = ROOT / "examples" / "demo_all_families.json"


def test_registry_resolves_every_v1_family():
    assert set(families()) == {
        "pressure_vessel",
        "piping",
        "flange",
        "storage_tank",
        "heat_exchanger",
        "column",
        "pump",
    }
    for family in families():
        pack = get_pack_class(family)()
        assert pack.family == family


def test_cli_runs_all_families_end_to_end(tmp_path):
    rc = main(["calc", str(ALL_FAMILIES), "--out", str(tmp_path)])
    assert rc == 0
    for item_id in ("L-101", "FL-101", "TK-101", "E-101", "C-101", "P-101"):
        item = tmp_path / item_id
        for name in ("results.json", "report.html", "report.pdf", "results.csv"):
            path = item / name
            assert path.is_file() and path.stat().st_size > 0, f"{item_id}/{name}"


def test_pump_family_emits_ga_drawing_and_datasheet(tmp_path):
    main(["calc", str(ALL_FAMILIES), "--out", str(tmp_path)])
    for name in ("drawing.dxf", "drawing.pdf", "datasheet.csv", "datasheet.pdf"):
        path = tmp_path / "P-101" / name
        assert path.is_file() and path.stat().st_size > 0, name
    csv_rows = (tmp_path / "P-101" / "datasheet.csv").read_text(encoding="utf-8").splitlines()
    assert csv_rows[0] == "Field,Value"
    assert len(csv_rows) > 10


def test_experimental_families_are_badged_in_the_report(tmp_path):
    main(["calc", str(ALL_FAMILIES), "--out", str(tmp_path)])
    for item_id in ("TK-101", "E-101", "C-101"):
        html = (tmp_path / item_id / "report.html").read_text(encoding="utf-8")
        assert "experimental" in html.lower(), item_id


def test_csv_export_has_one_row_per_result(tmp_path):
    import csv
    import io

    main(["calc", str(ALL_FAMILIES), "--out", str(tmp_path)])
    text = (tmp_path / "FL-101" / "results.csv").read_text(encoding="utf-8")
    rows = list(csv.reader(io.StringIO(text)))
    tree = json.loads((tmp_path / "FL-101" / "results.json").read_text(encoding="utf-8"))

    def flatten_count(nodes: list[dict]) -> int:
        return sum(1 + flatten_count(node["children"]) for node in nodes)

    assert rows[0][0] == "Symbol"
    assert len(rows) - 1 == flatten_count(tree["roots"])
