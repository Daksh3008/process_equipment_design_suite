"""PNG rendering for preview scenes (FR-3D 3D-2 evidence path).

The figure is built on a plain :class:`matplotlib.figure.Figure` with the
non-interactive Agg canvas, so the CLI can render without a display and the Qt
viewer reuses the same :func:`plot_scene` call. No randomness and no system
timestamps: the same scene renders the same pixels.
"""

from __future__ import annotations

from pathlib import Path

from matplotlib import colors as _mcolors
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d.art3d import (  # type: ignore[import-untyped]  # no stubs shipped
    Poly3DCollection,
)

from .scene import Scene

#: Locked role colours. Neutral geometry, one amber accent for connections,
#: one darker tier for the support — the accent carries meaning, not decoration.
ROLE_COLOR = {
    "shell": "#8a95a5",
    "head_bottom": "#8a95a5",
    "head_top": "#8a95a5",
    "nozzle": "#e07b00",
    "skirt": "#5b6b7c",
}
_EDGE = "#1f2933"
#: Fixed light direction so shading is deterministic across renders.
_LIGHT = (0.35, -0.45, 0.82)


def figure_for_scene(
    scene: Scene,
    *,
    title: str | None = None,
    azimuth: float = 45.0,
    elevation: float = 20.0,
    width: float = 10.0,
    height: float = 7.0,
) -> Figure:
    """Build a matplotlib figure with the scene plotted; the caller draws it."""
    fig = Figure(figsize=(width, height), facecolor="white")
    fig.canvas = FigureCanvasAgg(fig)
    ax = fig.add_subplot(111, projection="3d")
    plot_scene(ax, scene, title=title, azimuth=azimuth, elevation=elevation)
    return fig


def plot_scene(
    ax,
    scene: Scene,
    *,
    title: str | None = None,
    azimuth: float = 45.0,
    elevation: float = 20.0,
) -> None:
    """Plot *scene* onto an existing 3D axes with a fixed framing.

    All meshes go into a *single* collection so matplotlib depth-sorts the whole
    scene together; separate collections would let a near shell wall paint over
    a nozzle that sits on the near face (z-fighting between collections).
    """
    polygons: list[list[tuple[float, float, float]]] = []
    facecolors: list[tuple[float, float, float, float]] = []
    for mesh in scene.meshes:
        rgba = _mcolors.to_rgba(ROLE_COLOR.get(mesh.role, ROLE_COLOR["shell"]))
        for polygon in _polygons(mesh):
            polygons.append(polygon)
            facecolors.append(_lambert(polygon, rgba))
    ax.add_collection3d(
        Poly3DCollection(
            polygons,
            facecolors=facecolors,
            edgecolor=(0.12, 0.16, 0.20, 0.35),
            linewidth=0.35,
        )
    )
    _frame(ax, scene.bounds())
    ax.view_init(elev=elevation, azim=azimuth)
    ax.set_axis_off()
    if title:
        ax.set_title(title, fontsize=11, loc="left", pad=8)


def _polygons(mesh) -> list[list[tuple[float, float, float]]]:
    return [[mesh.vertices[index] for index in face] for face in mesh.faces]


def _lambert(
    polygon: list[tuple[float, float, float]],
    rgba: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    """Return *rgba* scaled by a fixed-direction diffuse term (deterministic)."""
    p0, p1, p2 = polygon[0], polygon[1], polygon[2]
    u = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
    v = (p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2])
    cross = (
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    )
    length = (cross[0] ** 2 + cross[1] ** 2 + cross[2] ** 2) ** 0.5
    if length <= 0.0:
        factor = 0.8
    else:
        normal = (cross[0] / length, cross[1] / length, cross[2] / length)
        dot = (
            normal[0] * _LIGHT[0] + normal[1] * _LIGHT[1] + normal[2] * _LIGHT[2]
        )
        factor = 0.55 + 0.45 * max(0.0, dot)
    return (rgba[0] * factor, rgba[1] * factor, rgba[2] * factor, rgba[3])


def _frame(ax, bounds: tuple[float, float, float, float, float, float]) -> None:
    """Center the axes on the scene with a cube viewport so aspect is equal."""
    centre = (
        (bounds[0] + bounds[1]) / 2.0,
        (bounds[2] + bounds[3]) / 2.0,
        (bounds[4] + bounds[5]) / 2.0,
    )
    extent = max(bounds[1] - bounds[0], bounds[3] - bounds[2], bounds[5] - bounds[4], 1.0)
    half = extent / 2.0 * 1.05
    ax.set_xlim3d(centre[0] - half, centre[0] + half)
    ax.set_ylim3d(centre[1] - half, centre[1] + half)
    ax.set_zlim3d(centre[2] - half, centre[2] + half)
    ax.set_box_aspect((1.0, 1.0, 1.0))


def render_png(
    scene: Scene,
    path: str | Path,
    *,
    title: str | None = None,
    azimuth: float = 45.0,
    elevation: float = 20.0,
    dpi: int = 110,
    width: float = 10.0,
    height: float = 7.0,
) -> Path:
    """Render *scene* to a PNG file and return the written path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig = figure_for_scene(
        scene, title=title, azimuth=azimuth, elevation=elevation, width=width, height=height
    )
    fig.savefig(out, dpi=dpi, facecolor="white", edgecolor="none", bbox_inches="tight")
    return out