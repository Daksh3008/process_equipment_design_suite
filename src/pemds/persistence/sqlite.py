"""SQLite project store (S5-1-T2).

Alongside the portable JSON file, projects can be persisted in a single SQLite
database keyed by project name. All access is parameterised; the JSON document is
stored verbatim so the two stores agree.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Self

from .project import SCHEMA_VERSION, Project
from .store import ProjectError

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    name TEXT PRIMARY KEY,
    schema_version INTEGER NOT NULL,
    modified TEXT NOT NULL DEFAULT '',
    document TEXT NOT NULL
)
"""


class SQLiteProjectStore:
    """A named collection of projects stored in one SQLite database."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(self.path))
        self._connection.execute(_SCHEMA)
        self._connection.commit()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self._connection.close()

    def save(self, project: Project) -> None:
        self._connection.execute(
            "INSERT INTO projects (name, schema_version, modified, document) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET schema_version=excluded.schema_version, "
            "modified=excluded.modified, document=excluded.document",
            (project.name, project.schema_version, project.modified, project.model_dump_json()),
        )
        self._connection.commit()

    def load(self, name: str) -> Project:
        row = self._connection.execute(
            "SELECT schema_version, document FROM projects WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            raise ProjectError(f"no project named {name!r} in {self.path}")
        schema_version, document = row
        if int(schema_version) > SCHEMA_VERSION:
            raise ProjectError(
                f"{name!r}: schema version {schema_version} is newer than supported {SCHEMA_VERSION}"
            )
        try:
            project = Project.model_validate(json.loads(document))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ProjectError(f"{name!r}: stored project is corrupt: {exc}") from exc
        return project

    def names(self) -> list[str]:
        return [row[0] for row in self._connection.execute("SELECT name FROM projects ORDER BY name")]
