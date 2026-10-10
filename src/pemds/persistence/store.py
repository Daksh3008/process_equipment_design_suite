"""Project store: atomic save/load, autosave and crash recovery (PM-1, NFR-6)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .project import Project


class ProjectError(Exception):
    """A project file is missing, malformed, or from a newer schema."""


class ProjectStore:
    """Reads and writes a project and its autosave companion."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    @property
    def autosave_path(self) -> Path:
        return self.path.with_suffix(self.path.suffix + ".autosave")

    def save(self, project: Project) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write_atomic(self.path, project)

    def autosave(self, project: Project) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._write_atomic(self.autosave_path, project)

    def load(self) -> Project:
        return self._read(self.path)

    def recover(self) -> Project | None:
        """Return the autosave if it exists and is newer than the project file."""
        if not self.autosave_path.is_file():
            return None
        if self.path.is_file() and self.path.stat().st_mtime >= self.autosave_path.stat().st_mtime:
            return None
        return self._read(self.autosave_path)

    def clear_autosave(self) -> None:
        if self.autosave_path.is_file():
            self.autosave_path.unlink()

    def _read(self, path: Path) -> Project:
        if not path.is_file():
            raise ProjectError(f"project file not found: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise ProjectError(f"{path}: invalid JSON: {exc}") from exc
        try:
            project = Project.model_validate(payload)
        except ValueError as exc:
            raise ProjectError(f"{path}: invalid project document: {exc}") from exc
        from .project import SCHEMA_VERSION

        if project.schema_version > SCHEMA_VERSION:
            raise ProjectError(
                f"{path}: schema version {project.schema_version} is newer than supported "
                f"{SCHEMA_VERSION}"
            )
        return project

    def _write_atomic(self, path: Path, project: Project) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            tmp.write_text(project.model_dump_json(indent=2), encoding="utf-8")
            os.replace(tmp, path)
        finally:
            if tmp.exists():
                tmp.unlink()
