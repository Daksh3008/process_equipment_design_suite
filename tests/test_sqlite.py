"""SQLite project store tests (S5-1-T2)."""

from __future__ import annotations

import sqlite3

import pytest

from pemds.persistence import EquipmentItem, Project, SQLiteProjectStore
from pemds.persistence.store import ProjectError


def _project(name: str = "Demo") -> Project:
    return Project(
        name=name,
        equipment=[EquipmentItem(id="V-101", family="pressure_vessel", inputs={"tag": "V-101"})],
    )


def test_sqlite_round_trip_and_upsert(tmp_path):
    with SQLiteProjectStore(tmp_path / "projects.db") as store:
        store.save(_project("A"))
        assert store.names() == ["A"]
        assert store.load("A") == _project("A")

        replacement = Project(name="A")
        store.save(replacement)
        assert store.load("A") == replacement


def test_sqlite_missing_project_reports_error(tmp_path):
    with SQLiteProjectStore(tmp_path / "projects.db") as store, pytest.raises(
        ProjectError, match="no project named"
    ):
        store.load("nope")


def test_sqlite_corrupt_document_reports_error(tmp_path):
    path = tmp_path / "projects.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE projects (name TEXT PRIMARY KEY, schema_version INTEGER NOT NULL, "
            "modified TEXT NOT NULL DEFAULT '', document TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO projects (name, schema_version, document) VALUES ('X', 1, '{not json')"
        )
    with SQLiteProjectStore(path) as store, pytest.raises(ProjectError, match="corrupt"):
        store.load("X")
