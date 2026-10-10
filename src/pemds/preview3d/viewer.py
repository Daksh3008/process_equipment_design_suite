"""Qt viewer for the 3D preview (FR-3D 3D-1).

A thin PySide6 wrapper around a matplotlib 3D axes: orbit/pan/zoom come from
matplotlib's mouse handling and the navigation toolbar, and the scene is
rebuilt from the same parameters as the results, so sliding an input and
recalculating regenerates the preview (3D-2). The widget imports Qt only on
construction, so the scene/PNG/STL stack stays importable headless.
"""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..core.result import ResultTree
from .render import plot_scene
from .scene import Scene, vessel_scene_from


class Preview3DWidget(QWidget):
    """Interactive preview panel hosted in the GUI's 3D tab."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from matplotlib.backends.backend_qtagg import (
            FigureCanvasQTAgg,
            NavigationToolbar2QT,
        )
        from matplotlib.figure import Figure

        self._figure = Figure(figsize=(7.0, 5.5), facecolor="white")
        self._canvas = FigureCanvasQTAgg(self._figure)
        toolbar = NavigationToolbar2QT(self._canvas, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(toolbar)
        layout.addWidget(self._canvas, 1)

    def show_scene(self, scene: Scene, title: str | None = None) -> None:
        """Render *scene*; replaces the previous preview in place."""
        self._figure.clear()
        ax = self._figure.add_subplot(111, projection="3d")
        plot_scene(ax, scene, title=title)
        self._canvas.draw_idle()

    def show_vessel(self, inputs, tree: ResultTree) -> None:
        """Build a scene from pack inputs/results and render it (3D-2)."""
        self.show_scene(vessel_scene_from(inputs, tree), title=f"{inputs.tag} — preview")

    def clear(self, message: str = "") -> None:
        """Reset the preview to an empty panel, optionally with an explanatory note."""
        self._figure.clear()
        ax = self._figure.add_subplot(111)
        ax.axis("off")
        if message:
            ax.text(0.5, 0.5, message, ha="center", va="center", wrap=True)
        self._canvas.draw_idle()