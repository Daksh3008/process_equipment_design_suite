"""Editing session with undo/redo and timed autosave (PM-1, PM-2, NFR-6)."""

from __future__ import annotations

import time
from collections.abc import Callable

from .project import Project
from .store import ProjectStore


class Session:
    """Holds the current project, an undo/redo history and an autosave timer.

    Edits are applied through :meth:`edit`, which snapshots the project before
    mutation so undo is exact. The clock is injectable for deterministic tests.
    """

    def __init__(
        self,
        project: Project,
        *,
        autosave_interval_s: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if autosave_interval_s <= 0:
            raise ValueError(f"autosave_interval_s must be > 0, got {autosave_interval_s}")
        self._project = project.model_copy(deep=True)
        self._undo: list[Project] = []
        self._redo: list[Project] = []
        self._autosave_interval_s = autosave_interval_s
        self._clock = clock
        self._last_autosave = clock()

    @property
    def project(self) -> Project:
        return self._project

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo)

    def edit(self, mutate: Callable[[Project], None]) -> None:
        """Apply *mutate* to the project, recording an undo snapshot."""
        snapshot = self._project.model_copy(deep=True)
        mutate(self._project)
        self._undo.append(snapshot)
        self._redo.clear()

    def undo(self) -> Project:
        if not self._undo:
            raise IndexError("nothing to undo")
        self._redo.append(self._project)
        self._project = self._undo.pop()
        return self._project

    def redo(self) -> Project:
        if not self._redo:
            raise IndexError("nothing to redo")
        self._undo.append(self._project)
        self._project = self._redo.pop()
        return self._project

    def maybe_autosave(self, store: ProjectStore) -> bool:
        """Autosave when the interval has elapsed. Returns whether it saved."""
        now = self._clock()
        if now - self._last_autosave < self._autosave_interval_s:
            return False
        store.autosave(self._project)
        self._last_autosave = now
        return True
