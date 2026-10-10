"""Preview exporters (FR-3D 3D-4 partial).

A binary STL writer for the preview scene. Normals are recomputed from the
triangle winding by the right-hand rule and degenerate (zero-area) triangles
are dropped. This is a *preview* export — the scene is not guaranteed
watertight for 3D printing, and the header records the triangle count so the
consumer knows what was produced.
"""

from __future__ import annotations

import math
import struct
from pathlib import Path

from .scene import Scene


def write_stl(scene: Scene, path: str | Path, *, label: str = "PEMDS preview") -> Path:
    """Write *scene* as a binary STL file and return the written path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    triangles: list[tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]] = []
    for mesh in scene.meshes:
        for a, b, c in mesh.faces:
            p0 = mesh.vertices[a]
            p1 = mesh.vertices[b]
            p2 = mesh.vertices[c]
            normal = _facet_normal(p0, p1, p2)
            if normal is None:
                continue
            triangles.append((normal, p0, p1, p2))

    header = (
        f"{label} | {scene.tag} | {scene.orientation} | {len(triangles)} triangles"[:80]
        if len(triangles) > 0
        else f"{label} | {scene.tag} | {scene.orientation}"
    )
    header_bytes = header.encode("ascii", errors="replace")[:80]
    with out.open("wb") as handle:
        handle.write(header_bytes + b"\x00" * (80 - len(header_bytes)))
        handle.write(struct.pack("<I", len(triangles)))
        for normal, p0, p1, p2 in triangles:
            handle.write(
                struct.pack(
                    "<12fH",
                    normal[0], normal[1], normal[2],
                    p0[0], p0[1], p0[2],
                    p1[0], p1[1], p1[2],
                    p2[0], p2[1], p2[2],
                    0,
                )
            )
    return out


def _facet_normal(
    p0: tuple[float, float, float],
    p1: tuple[float, float, float],
    p2: tuple[float, float, float],
) -> tuple[float, float, float] | None:
    """Unit normal by the right-hand rule, or None for a degenerate facet."""
    u = (p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2])
    v = (p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2])
    cross = (
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    )
    length = math.sqrt(cross[0] ** 2 + cross[1] ** 2 + cross[2] ** 2)
    if length <= 0.0:
        return None
    return (cross[0] / length, cross[1] / length, cross[2] / length)