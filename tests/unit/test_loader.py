"""Data loader and provenance tests (CIT-2, spec section 6)."""

from __future__ import annotations

import json

import pytest

from pemds.data.loader import DataError, load_package_data, load_path


def test_package_data_loads():
    data_file = load_package_data("codes/editions.json")
    assert data_file.provenance.source
    assert data_file.data["editions"]


def test_missing_provenance_is_rejected(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"materials": []}), encoding="utf-8")
    with pytest.raises(DataError, match="missing 'provenance'"):
        load_path(bad)


def test_incomplete_provenance_is_rejected(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps({"provenance": {"source": "x"}, "materials": []}), encoding="utf-8"
    )
    with pytest.raises(DataError, match="missing required keys"):
        load_path(bad)


def test_invalid_json_is_rejected(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(DataError, match="invalid JSON"):
        load_path(bad)
