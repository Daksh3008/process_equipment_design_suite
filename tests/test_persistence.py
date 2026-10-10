"""Persistence, undo/redo, autosave and crash recovery tests (PM-1..PM-4, NFR-6)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from pemds.persistence import Project, ProjectStore, Session
from pemds.persistence.store import ProjectError


def _project() -> Project:
    from pemds.persistence import EquipmentItem

    return Project(
        name="Demo",
        equipment=[EquipmentItem(id="V-101", family="pressure_vessel", inputs={"tag": "V-101"})],
    )


def test_save_load_round_trip(tmp_path):
    store = ProjectStore(tmp_path / "p.json")
    project = _project()
    store.save(project)
    assert store.load() == project


def test_undo_redo():
    session = Session(_project())
    session.edit(lambda p: p.equipment[0].inputs.__setitem__("tag", "V-102"))
    assert session.project.equipment[0].inputs["tag"] == "V-102"
    session.undo()
    assert session.project.equipment[0].inputs["tag"] == "V-101"
    session.redo()
    assert session.project.equipment[0].inputs["tag"] == "V-102"


def test_autosave_respects_interval(tmp_path):
    clock = _FakeClock()
    session = Session(_project(), autosave_interval_s=60.0, clock=clock)
    store = ProjectStore(tmp_path / "p.json")
    assert session.maybe_autosave(store) is False
    clock.t = 61.0
    assert session.maybe_autosave(store) is True
    assert store.autosave_path.is_file()


def test_recover_returns_newer_autosave(tmp_path):
    store = ProjectStore(tmp_path / "p.json")
    store.save(_project())
    newer = Project(name="Recovered")
    store.autosave(newer)
    base = Path(store.path)
    os.utime(base, (1.0, 1.0))
    os.utime(store.autosave_path, (2.0, 2.0))
    recovered = store.recover()
    assert recovered is not None
    assert recovered.name == "Recovered"


def test_recover_returns_none_when_autosave_older(tmp_path):
    store = ProjectStore(tmp_path / "p.json")
    store.save(_project())
    store.autosave(Project(name="Stale"))
    os.utime(store.path, (2.0, 2.0))
    os.utime(store.autosave_path, (1.0, 1.0))
    assert store.recover() is None


def test_newer_schema_is_rejected(tmp_path):
    path = tmp_path / "future.json"
    path.write_text(json.dumps({"name": "x", "schema_version": 99}), encoding="utf-8")
    with pytest.raises(ProjectError, match="newer than supported"):
        ProjectStore(path).load()


def test_wrong_shape_document_is_project_error(tmp_path):
    path = tmp_path / "wrong.json"
    path.write_text(json.dumps({"name": 5, "equipment": []}), encoding="utf-8")
    with pytest.raises(ProjectError, match="invalid project document"):
        ProjectStore(path).load()


class _FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t
