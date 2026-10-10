"""3D preview tests (FR-3D 3D-1/3D-2, 3D-4 partial; VAL-1 style concrete checks)."""

from __future__ import annotations

import struct
import time

import pytest

from pemds.packs.pv import PressureVesselPack
from pemds.packs.pv.model import VesselInputs
from pemds.preview3d.export import write_stl
from pemds.preview3d.render import render_png
from pemds.preview3d.scene import (
    Scene,
    cylinder_mesh,
    head_profile,
    revolution_mesh,
    tube_mesh,
    vessel_scene_from,
)

_BASE = dict(  # noqa: C408 - keyword form reads better for a fixture
    tag="V-101",
    orientation="vertical",
    inside_diameter_mm=2000.0,
    tangent_to_tangent_mm=4000.0,
    material_key="SA-516-70",
    head_material_key="SA-516-70",
    head_type="ellipsoidal",
    design_pressure_mpa=1.0,
    design_temperature_c=150.0,
    corrosion_allowance_mm=3.0,
    provided_shell_thickness_mm=16.0,
    provided_head_thickness_mm=16.0,
    support_type="skirt",
    support_height_mm=1200.0,
    nozzles=[
        {"tag": "N1", "outside_diameter_mm": 219.1, "provided_neck_thickness_mm": 8.18, "projection_mm": 300.0, "elevation_mm": 800.0, "azimuth_deg": 0.0},
        {"tag": "N2", "outside_diameter_mm": 168.3, "provided_neck_thickness_mm": 7.11, "projection_mm": 250.0, "elevation_mm": 1800.0, "azimuth_deg": 90.0},
        {"tag": "N3", "outside_diameter_mm": 114.3, "provided_neck_thickness_mm": 6.02, "projection_mm": 200.0, "elevation_mm": 1200.0, "azimuth_deg": 180.0},
    ],
)


def _scene(ctx, inputs: VesselInputs | None = None) -> Scene:
    inputs = inputs or VesselInputs(**_BASE)
    return vessel_scene_from(inputs, PressureVesselPack().calculate(inputs, ctx))


def test_scene_has_shell_heads_nozzles_and_skirt(ctx):
    labels = [mesh.label for mesh in _scene(ctx).meshes]
    assert labels[0] == "shell"
    assert set(labels[:3]) == {"shell", "head_top", "head_bottom"}
    assert {"nozzle N1", "nozzle N2", "nozzle N3", "skirt"} <= set(labels)


def test_scene_dimensions_are_exact(ctx):
    scene = _scene(ctx)
    min_x, max_x, min_y, max_y, min_z, max_z = scene.bounds()
    # Shell outside diameter 2032 mm; N1 projects 300 mm from +X and N3 200 mm from -X.
    assert max_x - min_x == pytest.approx(2032.0 + 300.0 + 200.0)
    # N2 projects 250 mm from +Y; the skirt base plate (1016+40) bounds the -Y side.
    assert max_y - min_y == pytest.approx(1266.0 + 1056.0)
    # Overall height = tangent 4000 + 2*500 head + skirt 1200; the base plate
    # sits flush at the skirt bottom, matching the 2D GA's 6200 mm span.
    assert max_z - min_z == pytest.approx(6200.0)


def test_meshes_are_consistent_and_finite(ctx):
    scene = _scene(ctx)
    assert scene.all_vertices_are_finite()
    assert scene.faces_are_in_range()
    for mesh in scene.meshes:
        assert mesh.size()[0] > 0 and mesh.size()[1] > 0


def test_scene_is_deterministic(ctx):
    first = _scene(ctx)
    second = _scene(ctx)
    for a, b in zip(first.meshes, second.meshes):
        assert a.vertices == b.vertices
        assert a.faces == b.faces


def test_nozzle_meshes_are_absent_when_there_are_none(ctx):
    inputs = VesselInputs(**{**_BASE, "nozzles": []})
    labels = [mesh.label for mesh in _scene(ctx, inputs).meshes]
    assert not any(label.startswith("nozzle") for label in labels)


def test_horizontal_orientation_puts_the_axis_along_y(ctx):
    inputs = VesselInputs(**{**_BASE, "orientation": "horizontal", "support_type": "none"})
    min_x, max_x, min_y, max_y, _min_z, _max_z = _scene(ctx, inputs).bounds()
    assert (max_y - min_y) > (max_x - min_x)  # long axis is now Y
    assert max_y - min_y == pytest.approx(5000.0)  # overall length along the axis
    assert max_x - min_x == pytest.approx(2032.0 + 300.0 + 200.0)  # nozzles on X


def test_head_profile_apex_is_exactly_zero_radius():
    profile = head_profile(1000.0, 250.0, 8)
    assert profile[0] == (1000.0, 0.0)
    assert profile[-1] == (0.0, 250.0)


def test_invalid_geometry_is_rejected():
    with pytest.raises(ValueError):
        cylinder_mesh(1.0, 5.0, 1.0, label="x", role="shell")
    with pytest.raises(ValueError):
        tube_mesh((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 1.0, label="x", role="nozzle")
    with pytest.raises(ValueError):
        revolution_mesh([(1.0, 0.0), (1.0, 1.0)], label="x", role="head")
    with pytest.raises(ValueError):
        Scene("t", "vertical", ()).bounds()


def test_flat_head_scene_is_supported(ctx):
    inputs = VesselInputs(**{**_BASE, "head_type": "flat", "support_type": "none", "nozzles": []})
    scene = _scene(ctx, inputs)
    assert scene.all_vertices_are_finite() and scene.faces_are_in_range()


def test_png_render_is_written_and_shows_geometry(ctx, tmp_path):
    from PIL import Image

    out = render_png(_scene(ctx), tmp_path / "preview.png", title="V-101 preview")
    assert out.is_file() and out.stat().st_size > 5000
    image = Image.open(out).convert("RGB")
    pixels = image.load()
    width, height = image.size
    assert pixels[2, 2] == (255, 255, 255)
    drawn = sum(1 for x in range(0, width, 2) for y in range(0, height, 2) if pixels[x, y] != (255, 255, 255))
    assert drawn > 500  # the vessel silhouette occupies a real share of the frame


def test_png_render_is_deterministic(ctx, tmp_path):
    first = render_png(_scene(ctx), tmp_path / "a.png", title="V-101 preview")
    second = render_png(_scene(ctx), tmp_path / "b.png", title="V-101 preview")
    assert first.read_bytes() == second.read_bytes()


def test_nozzles_show_the_accent_colour(ctx, tmp_path):
    from PIL import Image

    out = render_png(_scene(ctx), tmp_path / "n.png", azimuth=-90.0, elevation=25.0)
    image = Image.open(out).convert("RGB")
    pixels = image.load()
    width, height = image.size
    warm = sum(
        1
        for x in range(width)
        for y in range(height)
        if pixels[x, y][0] > 140
        and pixels[x, y][0] > pixels[x, y][1] > pixels[x, y][2]
        and pixels[x, y][2] < 120
    )
    assert warm > 5  # amber nozzle ink is present, not only the neutral shell


def test_stl_export_round_trips(ctx, tmp_path):
    scene = _scene(ctx)
    expected_triangles = scene.size()[1]
    path = write_stl(scene, tmp_path / "preview.stl")
    data = path.read_bytes()
    assert struct.unpack("<I", data[80:84])[0] == expected_triangles
    assert len(data) == 84 + 50 * expected_triangles
    normal = struct.unpack("<3f", data[84:96])
    length = sum(component * component for component in normal) ** 0.5
    assert length == pytest.approx(1.0, abs=1e-6)


def test_scene_build_is_fast(ctx):
    inputs = VesselInputs(**_BASE)
    tree = PressureVesselPack().calculate(inputs, ctx)
    start = time.perf_counter()
    vessel_scene_from(inputs, tree)
    assert time.perf_counter() - start < 2.0