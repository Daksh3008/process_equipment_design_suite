"""Report and drawing generation tests (RP-1, DR-1..DR-5)."""

from __future__ import annotations

import re
import zlib
from pathlib import Path

import ezdxf

from pemds.drawing.ga import vessel_ga_from, write_dxf, write_pdf
from pemds.packs.pv import PressureVesselPack
from pemds.packs.pv.model import VesselInputs
from pemds.report.engine import render_html, render_pdf

_KWARGS = dict(  # noqa: C408 - keyword form reads better for a fixture
    tag="V-101",
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
)


def _tree(ctx):
    inputs = VesselInputs(**_KWARGS)
    return inputs, PressureVesselPack().calculate(inputs, ctx)


def test_html_report_contains_trace_and_disclaimer(ctx):
    inputs, tree = _tree(ctx)
    html = render_html(
        project_name="Demo", equipment_id="V-101", family="pressure_vessel", inputs=inputs, tree=tree
    )
    assert "UG-98" in html
    assert "Tool-assisted calculation" in html
    assert "1.739 MPa" in html  # MAWP in display units (as-built metal, 12.7 mm)
    assert "PASS" in html
    assert "provisional" in html  # UNVERIFIED material data is surfaced in the report


def test_pdf_report_written(ctx, tmp_path):
    inputs, tree = _tree(ctx)
    path = render_pdf(
        project_name="Demo",
        equipment_id="V-101",
        family="pressure_vessel",
        inputs=inputs,
        tree=tree,
        path=tmp_path / "report.pdf",
    )
    assert path.is_file() and path.stat().st_size > 1000


def test_dxf_drawing_has_layers(ctx, tmp_path):
    inputs, tree = _tree(ctx)
    ga = vessel_ga_from(inputs, tree)
    path = write_dxf(ga, tmp_path / "drawing.dxf")
    doc = ezdxf.readfile(path)
    names = {layer.dxf.name for layer in doc.layers}
    assert {"GEOMETRY", "DIMENSIONS", "ANNOTATION", "TITLEBLOCK", "CENTERLINE"} <= names
    assert len(list(doc.modelspace())) > 10


def test_pdf_drawing_written(ctx, tmp_path):
    inputs, tree = _tree(ctx)
    ga = vessel_ga_from(inputs, tree)
    path = write_pdf(ga, tmp_path / "drawing.pdf")
    assert path.is_file() and path.stat().st_size > 500


def test_drawing_shows_nozzles_and_skirt(ctx, tmp_path):
    inputs = VesselInputs(
        **{
            **_KWARGS,
            "support_type": "skirt",
            "support_height_mm": 1200.0,
            "nozzles": [
                {
                    "tag": "N1",
                    "outside_diameter_mm": 219.1,
                    "provided_neck_thickness_mm": 8.18,
                    "projection_mm": 300.0,
                    "elevation_mm": 800.0,
                    "azimuth_deg": 0.0,
                    "service": "process inlet",
                }
            ],
        }
    )
    tree = PressureVesselPack().calculate(inputs, ctx)
    ga = vessel_ga_from(inputs, tree)
    assert ga.skirt_height_mm == 1200.0
    assert [nozzle.tag for nozzle in ga.nozzles] == ["N1"]

    doc = ezdxf.readfile(write_dxf(ga, tmp_path / "nozzles.dxf"))
    texts = [entity.dxf.text for entity in doc.modelspace().query("TEXT")]
    assert any("N1" in text and "process inlet" in text for text in texts)

    pdf = write_pdf(ga, tmp_path / "nozzles.pdf")
    assert pdf.is_file() and pdf.stat().st_size > 500


def test_drawing_lays_a_horizontal_vessel_on_its_side(ctx, tmp_path):
    inputs = VesselInputs(**{**_KWARGS, "orientation": "horizontal", "support_type": "none"})
    tree = PressureVesselPack().calculate(inputs, ctx)
    ga = vessel_ga_from(inputs, tree)
    assert ga.orientation == "horizontal"

    doc = ezdxf.readfile(write_dxf(ga, tmp_path / "horizontal.dxf"))
    xs: list[float] = []
    ys: list[float] = []
    for entity in doc.modelspace():
        points: list[tuple[float, float]] = []
        if entity.dxftype() == "LWPOLYLINE":
            points = [(v[0], v[1]) for v in entity.get_points()]
        elif entity.dxftype() == "LINE":
            points = [(entity.dxf.start.x, entity.dxf.start.y), (entity.dxf.end.x, entity.dxf.end.y)]
        xs.extend(point[0] for point in points)
        ys.extend(point[1] for point in points)
    assert (max(xs) - min(xs)) > (max(ys) - min(ys))  # the axis runs along the sheet X

    pdf = write_pdf(ga, tmp_path / "horizontal.pdf")
    assert pdf.is_file() and pdf.stat().st_size > 500


def test_horizontal_pdf_content_differs_from_vertical(ctx, tmp_path):
    """The horizontal layout transposes the geometry in the PDF, not just DXF."""
    inputs_h = VesselInputs(**{**_KWARGS, "orientation": "horizontal", "support_type": "none"})
    inputs_v = VesselInputs(**{**_KWARGS, "support_type": "none"})
    tree_h = PressureVesselPack().calculate(inputs_h, ctx)
    tree_v = PressureVesselPack().calculate(inputs_v, ctx)
    h_path = write_pdf(vessel_ga_from(inputs_h, tree_h), tmp_path / "h.pdf")
    v_path = write_pdf(vessel_ga_from(inputs_v, tree_v), tmp_path / "v.pdf")

    def content_streams(path) -> bytes:
        data = Path(path).read_bytes()
        chunks = []
        for match in re.finditer(rb"stream\r?\n(.*?)endstream", data, re.DOTALL):
            raw = match.group(1)
            try:
                chunks.append(zlib.decompress(raw))
            except zlib.error:
                chunks.append(raw)
        return b"".join(chunks)

    horizontal = content_streams(h_path)
    vertical = content_streams(v_path)
    assert horizontal and vertical
    assert horizontal != vertical  # a PDF-only orientation regression now fails this
