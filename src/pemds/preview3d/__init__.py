"""3D preview (FR-3D 3D-1/3D-2, 3D-4 partial).

A geometry-preview sanity check generated from the same pack inputs and results
as the 2D GA drawing. The scene is pure geometry; rendering, Qt viewing and STL
export are separate consumers.
"""

from __future__ import annotations

from .export import write_stl
from .render import figure_for_scene, plot_scene, render_png
from .scene import Mesh, Scene, vessel_scene_from

__all__ = [
    "Mesh",
    "Scene",
    "figure_for_scene",
    "plot_scene",
    "render_png",
    "vessel_scene_from",
    "write_stl",
]