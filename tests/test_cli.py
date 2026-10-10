"""CLI end-to-end tests (gate 3: run the real path)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pemds.cli import main

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "demo_vessel.json"


def _inputs() -> dict:
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    return payload["equipment"][0]["inputs"]


def _write_project(path: Path, equipment: list[dict], name: str = "T") -> Path:
    path.write_text(json.dumps({"name": name, "equipment": equipment}), encoding="utf-8")
    return path


def test_cli_calc_writes_all_outputs(tmp_path):
    rc = main(["calc", str(EXAMPLE), "--out", str(tmp_path)])
    assert rc == 0
    item = tmp_path / "V-101"
    for name in (
        "results.json",
        "report.html",
        "report.pdf",
        "drawing.dxf",
        "drawing.pdf",
        "preview.png",
        "preview.stl",
    ):
        path = item / name
        assert path.is_file(), name
        assert path.stat().st_size > 0, name


def test_cli_empty_project_succeeds(tmp_path):
    project = _write_project(tmp_path / "empty.json", [])
    assert main(["calc", str(project), "--out", str(tmp_path / "out")]) == 0


def test_cli_malformed_project_reports_error(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert main(["calc", str(bad), "--out", str(tmp_path / "out")]) == 1


def test_cli_missing_project_reports_error(tmp_path):
    assert main(["calc", str(tmp_path / "missing.json"), "--out", str(tmp_path / "out")]) == 1


def test_cli_duplicate_ids_rejected(tmp_path):
    equipment = [
        {"id": "V-101", "family": "pressure_vessel", "inputs": _inputs()},
        {"id": "V-101", "family": "pressure_vessel", "inputs": _inputs()},
    ]
    project = _write_project(tmp_path / "dup.json", equipment)
    assert main(["calc", str(project), "--out", str(tmp_path / "out")]) == 1


def test_cli_unsafe_id_rejected(tmp_path):
    equipment = [{"id": "../evil", "family": "pressure_vessel", "inputs": _inputs()}]
    project = _write_project(tmp_path / "unsafe.json", equipment)
    assert main(["calc", str(project), "--out", str(tmp_path / "out")]) == 1
    assert not (tmp_path / "evil").exists()


@pytest.mark.parametrize(
    "bad_id", ["  ", "NUL", "V-101.", "V-101.staging", "a" * 101, "with space", "..evil"]
)
def test_cli_other_unsafe_ids_rejected(tmp_path, bad_id):
    equipment = [{"id": bad_id, "family": "pressure_vessel", "inputs": _inputs()}]
    project = _write_project(tmp_path / "unsafe2.json", equipment)
    assert main(["calc", str(project), "--out", str(tmp_path / "out")]) == 1


def test_cli_case_insensitive_duplicate_ids_rejected(tmp_path):
    equipment = [
        {"id": "V-101", "family": "pressure_vessel", "inputs": _inputs()},
        {"id": "v-101", "family": "pressure_vessel", "inputs": _inputs()},
    ]
    project = _write_project(tmp_path / "dup2.json", equipment)
    assert main(["calc", str(project), "--out", str(tmp_path / "out")]) == 1


def test_cli_unknown_family_reports_error(tmp_path):
    equipment = [{"id": "X-1", "family": "warp_core", "inputs": {}}]
    project = _write_project(tmp_path / "family.json", equipment)
    assert main(["calc", str(project), "--out", str(tmp_path / "out")]) == 1


def test_cli_validation_error_returns_one(tmp_path):
    inputs = _inputs()
    inputs["provided_shell_thickness_mm"] = 3.0  # below CA + mill tolerance
    equipment = [{"id": "V-101", "family": "pressure_vessel", "inputs": inputs}]
    project = _write_project(tmp_path / "invalid.json", equipment)
    assert main(["calc", str(project), "--out", str(tmp_path / "out")]) == 1


def test_cli_out_path_that_is_a_file_returns_one(tmp_path):
    blocker = tmp_path / "out"
    blocker.write_text("occupied", encoding="utf-8")
    assert main(["calc", str(EXAMPLE), "--out", str(blocker)]) == 1


def test_cli_validation_error_leaves_no_partial_output(tmp_path):
    inputs = _inputs()
    inputs["design_temperature_c"] = float("nan")
    equipment = [{"id": "V-101", "family": "pressure_vessel", "inputs": inputs}]
    project = _write_project(tmp_path / "nan.json", equipment)
    out = tmp_path / "out"
    assert main(["calc", str(project), "--out", str(out)]) == 1
    assert not (out / "V-101").exists()  # no staged/partial item directory
    assert not list(out.glob("*.staging"))


def test_cli_imperial_units_reach_the_report(tmp_path):
    assert main(["calc", str(EXAMPLE), "--out", str(tmp_path), "--units", "IMPERIAL"]) == 0
    html = (tmp_path / "V-101" / "report.html").read_text(encoding="utf-8")
    assert "psi" in html  # MAWP rendered in psi
    assert "78.74" in html  # 2000 mm inside diameter shown in inches
