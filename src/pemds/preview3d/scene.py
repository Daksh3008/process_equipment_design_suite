"""3D preview scene (FR-3D 3D-1/3D-2).

A :class:`Scene` is a collection of triangulated :class:`Mesh` objects in
millimetres, generated from the *same* pack inputs and result tree as the 2D GA
drawing — one parameter set, two renderings. The scene is pure geometry with
no rendering dependency: the Qt viewer, the PNG renderer and the STL exporter
live in sibling modules and consume it, which keeps this module unit-testable
and free of heavy imports.

Scope is deliberately preview-grade: the cylindrical shell, the formed heads,
a skirt support for vertical vessels, and the PV-3 nozzle schedule. This is a
geometry sanity-check, not a modeller (specification section 12).

Coordinate convention: the vessel axis runs along Z with the bottom tangent
line at z = 0 and the shell occupying ``0 <= z <= tangent_to_tangent``. A
horizontal vessel is rotated about X so its axis lies along Y; the finished
scene is re-centred on the origin so renderers can frame it without knowing the
support chain.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from ..core.geometry import (
    HEAD_DEPTH_FACTOR,
    SKIRT_BASE_OVERHANG_MM,
    provided_or_required_shell_mm,
)
from ..core.result import ResultTree


@dataclass(frozen=True)
class Mesh:
    """A labelled triangulated surface, in millimetres."""

    label: str
    role: str
    vertices: tuple[tuple[float, float, float], ...]
    faces: tuple[tuple[int, int, int], ...]

    def size(self) -> tuple[int, int]:
        """(vertex count, face count)."""
        return len(self.vertices), len(self.faces)

    def bounds(self) -> tuple[float, float, float, float, float, float]:
        """(min_x, max_x, min_y, max_y, min_z, max_z) over all vertices."""
        xs = [point[0] for point in self.vertices]
        ys = [point[1] for point in self.vertices]
        zs = [point[2] for point in self.vertices]
        return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


@dataclass(frozen=True)
class Scene:
    """A preview scene: a tagged vessel plus its meshes."""

    tag: str
    orientation: str
    meshes: tuple[Mesh, ...] = ()

    def size(self) -> tuple[int, int]:
        """Total (vertex count, face count) across all meshes."""
        vertices = sum(mesh.size()[0] for mesh in self.meshes)
        faces = sum(mesh.size()[1] for mesh in self.meshes)
        return vertices, faces

    def bounds(self) -> tuple[float, float, float, float, float, float]:
        """Union of the mesh bounds; raises if the scene is empty."""
        if not self.meshes:
            raise ValueError("cannot bound an empty scene")
        stacked = [mesh.bounds() for mesh in self.meshes]
        return (
            min(bounds[0] for bounds in stacked),
            max(bounds[1] for bounds in stacked),
            min(bounds[2] for bounds in stacked),
            max(bounds[3] for bounds in stacked),
            min(bounds[4] for bounds in stacked),
            max(bounds[5] for bounds in stacked),
        )

    def all_vertices_are_finite(self) -> bool:
        """Determinism guard: no NaN/Inf can enter the geometry silently."""
        for mesh in self.meshes:
            for x, y, z in mesh.vertices:
                if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
                    return False
        return True

    def faces_are_in_range(self) -> bool:
        """Consistency guard used by tests: every face index exists."""
        for mesh in self.meshes:
            count = len(mesh.vertices)
            for a, b, c in mesh.faces:
                if not (0 <= a < count and 0 <= b < count and 0 <= c < count):
                    return False
        return True


def _ring(radius: float, z: float, segments: int) -> list[tuple[float, float, float]]:
    points: list[tuple[float, float, float]] = []
    for index in range(segments):
        angle = 2.0 * math.pi * index / segments
        points.append((radius * math.cos(angle), radius * math.sin(angle), z))
    return points


def _strip_faces(segments: int, ring_bottom: int, ring_top: int) -> list[tuple[int, int, int]]:
    """Triangulate between two vertex rings of equal size, kept consistently wound."""
    faces: list[tuple[int, int, int]] = []
    for index in range(segments):
        next_index = (index + 1) % segments
        b0 = ring_bottom + index
        b1 = ring_bottom + next_index
        t0 = ring_top + index
        t1 = ring_top + next_index
        faces.append((b0, t0, b1))
        faces.append((b1, t0, t1))
    return faces


def cylinder_mesh(
    radius: float,
    z0: float,
    z1: float,
    *,
    label: str,
    role: str,
    segments: int = 48,
    caps: bool = False,
) -> Mesh:
    """An open (optionally capped) cylinder whose axis is Z, from z0 to z1."""
    if z1 < z0:
        raise ValueError(f"cylinder z1 ({z1:g}) must be >= z0 ({z0:g})")
    bottom = _ring(radius, z0, segments)
    top = _ring(radius, z1, segments)
    vertices: list[tuple[float, float, float]] = [*bottom, *top]
    faces = _strip_faces(segments, 0, segments)
    if caps:
        b_center = len(vertices)
        vertices.append((0.0, 0.0, z0))
        t_center = len(vertices)
        vertices.append((0.0, 0.0, z1))
        for index in range(segments):
            next_index = (index + 1) % segments
            faces.append((index, next_index, b_center))
            faces.append((segments + index, segments + next_index, t_center))
    return Mesh(label=label, role=role, vertices=tuple(vertices), faces=tuple(faces))


def head_profile(radius: float, depth: float, steps: int = 16) -> list[tuple[float, float]]:
    """(r, z) outline of a head with the 2D drawing's elliptical bulge.

    Sampled rim (r = radius, z = 0) to apex (r = 0, z = depth) so a surface of
    revolution matches the elevation outline exactly, whatever the head type.
    """
    if radius <= 0:
        raise ValueError(f"radius must be > 0, got {radius:g}")
    if depth < 0:
        raise ValueError(f"depth must be >= 0, got {depth:g}")
    if steps < 2:
        raise ValueError(f"steps must be >= 2, got {steps}")
    points: list[tuple[float, float]] = []
    for index in range(steps):
        theta = 0.5 * math.pi * index / steps
        points.append((radius * math.cos(theta), depth * math.sin(theta)))
    points.append((0.0, depth))  # exact apex; cos(pi/2) is not exactly zero
    return points


def _fanned_strip(
    segments: int,
    ring_a: int,
    ring_b: int,
    apex_index: int,
) -> list[tuple[int, int, int]]:
    """Triangle strip between two rings, or a fan into the shared apex vertex."""
    faces: list[tuple[int, int, int]] = []
    if ring_b == apex_index:  # fan into the collapsed apex vertex
        for index in range(segments):
            next_index = (index + 1) % segments
            faces.append((ring_a + index, apex_index, ring_a + next_index))
        return faces
    for index in range(segments):
        next_index = (index + 1) % segments
        a0 = ring_a + index
        a1 = ring_a + next_index
        b0 = ring_b + index
        b1 = ring_b + next_index
        faces.append((a0, b0, a1))
        faces.append((a1, b0, b1))
    return faces


def revolution_mesh(
    profile: list[tuple[float, float]],
    *,
    label: str,
    role: str,
    segments: int = 48,
    z_offset: float = 0.0,
) -> Mesh:
    """Surface of revolution of *profile* (r, z) points about Z, apex last.

    The last profile point is the apex (r = 0) and collapses to one shared
    vertex, so the mesh is closed at that end and watertight together with the
    shell cylinder it shares its rim with.
    """
    if len(profile) < 2:
        raise ValueError(f"profile needs at least 2 points, got {len(profile)}")
    apex = profile[-1]
    if apex[0] != 0.0:
        raise ValueError(f"profile apex must have r == 0, got r={apex[0]:g}")
    rings = profile[:-1]
    vertices: list[tuple[float, float, float]] = []
    ring_offsets: list[int] = []
    for r, z in rings:
        ring_offsets.append(len(vertices))
        vertices.extend(
            (x, y, z + z_offset) for x, y, _z in _ring(r, z + z_offset, segments)
        )
    apex_offset = len(vertices)
    vertices.append((0.0, 0.0, apex[1] + z_offset))

    faces: list[tuple[int, int, int]] = []
    for index in range(len(rings) - 1):
        faces.extend(
            _fanned_strip(segments, ring_offsets[index], ring_offsets[index + 1], apex_offset)
        )
    # The final real ring fans into the shared apex vertex (closed end).
    faces.extend(_fanned_strip(segments, ring_offsets[-1], apex_offset, apex_offset))
    return Mesh(label=label, role=role, vertices=tuple(vertices), faces=tuple(faces))


def tube_mesh(
    start: tuple[float, float, float],
    end: tuple[float, float, float],
    radius: float,
    *,
    label: str,
    role: str,
    segments: int = 24,
) -> Mesh:
    """A capped open-ended tube from *start* to *end* (nozzle necks, stubs)."""
    direction = (end[0] - start[0], end[1] - start[1], end[2] - start[2])
    length = math.sqrt(direction[0] ** 2 + direction[1] ** 2 + direction[2] ** 2)
    if length <= 0:
        raise ValueError("tube start and end must differ")
    unit = (direction[0] / length, direction[1] / length, direction[2] / length)
    up = (0.0, 0.0, 1.0)
    if abs(unit[2]) > 0.99:
        up = (1.0, 0.0, 0.0)
    right = _cross(unit, up)
    right = (right[0] / _norm(right), right[1] / _norm(right), right[2] / _norm(right))
    forward = _cross(right, unit)

    def point(t: float, angle: float) -> tuple[float, float, float]:
        radial = (
            radius * (math.cos(angle) * right[0] + math.sin(angle) * forward[0]),
            radius * (math.cos(angle) * right[1] + math.sin(angle) * forward[1]),
            radius * (math.cos(angle) * right[2] + math.sin(angle) * forward[2]),
        )
        return (
            start[0] + unit[0] * t * length + radial[0],
            start[1] + unit[1] * t * length + radial[1],
            start[2] + unit[2] * t * length + radial[2],
        )

    vertices: list[tuple[float, float, float]] = []
    for angle_index in range(segments):
        angle = 2.0 * math.pi * angle_index / segments
        vertices.append(point(0.0, angle))
    for angle_index in range(segments):
        angle = 2.0 * math.pi * angle_index / segments
        vertices.append(point(1.0, angle))
    faces = _strip_faces(segments, 0, segments)
    start_center = len(vertices)
    vertices.append(start)
    end_center = len(vertices)
    vertices.append(end)
    for index in range(segments):
        next_index = (index + 1) % segments
        faces.append((index, next_index, start_center))
        faces.append((segments + index, end_center, segments + next_index))
    return Mesh(label=label, role=role, vertices=tuple(vertices), faces=tuple(faces))


def disc_mesh(
    radius: float,
    z: float,
    *,
    label: str,
    role: str,
    segments: int = 48,
) -> Mesh:
    """A flat circular disc at height z (skirt base ring)."""
    rim = _ring(radius, z, segments)
    center = len(rim)
    vertices = [*rim, (0.0, 0.0, z)]
    faces = [(index, next_index, center) for index, next_index in _adjacent(segments)]
    return Mesh(label=label, role=role, vertices=tuple(vertices), faces=tuple(faces))


def _adjacent(segments: int):
    for index in range(segments):
        yield index, (index + 1) % segments


def _cross(a, b) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm(vector) -> float:
    return math.sqrt(vector[0] ** 2 + vector[1] ** 2 + vector[2] ** 2)


def vessel_scene_from(
    inputs,
    tree: ResultTree,
    *,
    segments: int = 48,
    head_steps: int = 16,
) -> Scene:
    """Build the preview scene for a vessel from pack inputs and results."""
    diameter = inputs.inside_diameter_mm
    radius = diameter / 2.0
    tangent = inputs.tangent_to_tangent_mm
    shell_mm = _shell_thickness_mm(inputs, tree)
    outside_radius = radius + shell_mm
    depth = diameter * HEAD_DEPTH_FACTOR[inputs.head_type]

    meshes: list[Mesh] = [
        cylinder_mesh(
            outside_radius,
            0.0,
            tangent,
            label="shell",
            role="shell",
            segments=segments,
        ),
        _head_mesh(outside_radius, depth, "head_top", segments, head_steps, tangent),
        _head_mesh(outside_radius, depth, "head_bottom", segments, head_steps, 0.0),
    ]
    meshes.extend(_nozzle_meshes(inputs, outside_radius, segments))
    if inputs.support_type == "skirt" and inputs.orientation == "vertical":
        meshes.extend(_skirt_meshes(inputs, outside_radius, depth, segments))

    meshes = _orient(meshes, inputs.orientation)
    meshes = _centre(meshes)
    return Scene(tag=inputs.tag, orientation=inputs.orientation, meshes=tuple(meshes))


def _shell_thickness_mm(inputs, tree: ResultTree) -> float:
    return provided_or_required_shell_mm(inputs, tree)


def _head_mesh(
    radius: float,
    depth: float,
    role: str,
    segments: int,
    steps: int,
    tangent: float,
) -> Mesh:
    profile = head_profile(radius, depth, steps)
    if role == "head_bottom":
        profile = [(r, -z) for r, z in profile]
    return revolution_mesh(
        profile,
        label=role,
        role=role,
        segments=segments,
        z_offset=tangent if role == "head_top" else 0.0,
    )


def _nozzle_meshes(inputs, outside_radius: float, segments: int) -> list[Mesh]:
    meshes: list[Mesh] = []
    for nozzle in sorted(inputs.nozzles, key=lambda n: (n.elevation_mm, n.tag)):
        azimuth = math.radians(nozzle.azimuth_deg)
        direction = (math.cos(azimuth), math.sin(azimuth), 0.0)
        start = (
            outside_radius * direction[0],
            outside_radius * direction[1],
            nozzle.elevation_mm,
        )
        end = (
            start[0] + nozzle.projection_mm * direction[0],
            start[1] + nozzle.projection_mm * direction[1],
            start[2],
        )
        meshes.append(
            tube_mesh(
                start,
                end,
                nozzle.outside_diameter_mm / 2.0,
                label=f"nozzle {nozzle.tag}",
                role="nozzle",
                segments=max(12, segments // 2),
            )
        )
    return meshes


def _skirt_meshes(inputs, outside_radius: float, depth: float, segments: int) -> list[Mesh]:
    height = inputs.support_height_mm
    base_z = -depth - height
    width = SKIRT_BASE_OVERHANG_MM
    meshes = [
        cylinder_mesh(
            outside_radius,
            base_z,
            -depth,
            label="skirt",
            role="skirt",
            segments=segments,
        ),
        disc_mesh(
            outside_radius + width,
            base_z,
            label="base plate",
            role="skirt",
            segments=segments,
        ),
    ]
    return meshes


def _orient(meshes: list[Mesh], orientation: str) -> list[Mesh]:
    if orientation == "vertical":
        return meshes
    if orientation != "horizontal":
        raise ValueError(f"unsupported orientation {orientation!r}")

    def rotate(point: tuple[float, float, float]) -> tuple[float, float, float]:
        x, y, z = point
        return x, -z, y  # 90 deg about X: the vessel axis now runs along Y

    return [_map_mesh(mesh, rotate) for mesh in meshes]


def _centre(meshes: list[Mesh]) -> list[Mesh]:
    if not meshes:
        return meshes
    xs = [p[0] for mesh in meshes for p in mesh.vertices]
    ys = [p[1] for mesh in meshes for p in mesh.vertices]
    zs = [p[2] for mesh in meshes for p in mesh.vertices]
    centre = ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0, (min(zs) + max(zs)) / 2.0)

    def shift(point: tuple[float, float, float]) -> tuple[float, float, float]:
        return point[0] - centre[0], point[1] - centre[1], point[2] - centre[2]

    return [_map_mesh(mesh, shift) for mesh in meshes]


def _map_mesh(mesh: Mesh, transform: Callable[[tuple[float, float, float]], tuple[float, float, float]]) -> Mesh:
    return Mesh(
        label=mesh.label,
        role=mesh.role,
        vertices=tuple(transform(point) for point in mesh.vertices),
        faces=mesh.faces,
    )