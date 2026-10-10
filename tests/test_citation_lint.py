"""Tests for the citation/copyright lint (CIT-2, CIT-4)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "citation_lint", ROOT / "scripts" / "citation_lint.py"
)
assert _spec and _spec.loader
lint = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lint)


def test_repository_passes_all_gates():
    assert lint.run(ROOT) == []


def test_calc_citations_are_complete():
    assert lint.check_calc_citations() == []


def test_missing_provenance_header_detected(tmp_path):
    data = tmp_path / "src" / "pemds" / "data"
    data.mkdir(parents=True)
    (data / "bad.json").write_text(json.dumps({"materials": []}), encoding="utf-8")
    assert any("missing provenance" in v for v in lint.check_data_provenance(tmp_path))


def test_long_string_detected(tmp_path):
    data = tmp_path / "src" / "pemds" / "data"
    data.mkdir(parents=True)
    payload = {
        "provenance": {
            "source": "s",
            "edition": "e",
            "clause": "c",
            "licence": "l",
            "transcribed_on": "d",
            "checked_by": "x",
        },
        "text": "x" * 500,
    }
    (data / "long.json").write_text(json.dumps(payload), encoding="utf-8")
    assert any("long string literal" in v for v in lint.check_data_strings(tmp_path))
