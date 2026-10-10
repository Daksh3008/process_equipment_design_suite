"""GA drawing for a vertical pressure vessel (DR-1..DR-5).

Produces a parametric general-arrangement sketch as DXF (editable) and PDF
(print-ready). Geometry is generated from the same parameters as the
calculation. Layers follow a fixed scheme: GEOMETRY, DIMENSIONS, ANNOTATION,
CENTERLINE and TITLEBLOCK. Annotations are written in the user's display units.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

from ..core.geometry import (
    HEAD_DEPTH_FACTOR,
    SKIRT_BASE_OVERHANG_MM,
    provided_or_required_shell_mm,
)
from ..core.result import ResultTree
from ..core.units import UnitSystem, display_unit, format_value, from_base


@dataclass(frozen=True)
class NozzleGA:
    """One nozzle's drawing footprint (elevation view stub + callout)."""

    tag: str
    elevation_mm: float
    outside_diameter_mm: float
    projection_mm: float
    service: str = ""


@dataclass(frozen=True)
class VesselGA:
    """Geometry and annotations of a vessel GA sketch, in millimetres."""

    tag: str
    inside_diameter_mm: float
    tangent_to_tangent_mm: float
    shell_thickness_mm: float
    head_type: str
    unit_system: UnitSystem = UnitSystem.SI
    annotations: dict[str, str] = field(default_factory=dict)
    nozzles: tuple[NozzleGA, ...] = ()
    skirt_height_mm: float = 0.0
    orientation: str = "vertical"

    @property
    def head_depth_mm(self) -> float:
        return self.inside_diameter_mm * HEAD_DEPTH_FACTOR[self.head_type]

    @property
    def overall_length_mm(self) -> float:
        return self.tangent_to_tangent_mm + 2.0 * self.head_depth_mm

    @property
    def outside_radius_mm(self) -> float:
        return self.inside_diameter_mm / 2.0 + self.shell_thickness_mm

    @property
    def bottom_offset_mm(self) -> float:
        """Distance from the bottom tangent line to the lowest drawn feature."""
        return self.head_depth_mm + self.skirt_height_mm


def vessel_ga_from(inputs, tree: ResultTree, system: UnitSystem = UnitSystem.SI) -> VesselGA:
    """Build GA geometry from pack inputs and results."""
    annotations: dict[str, str] = {}
    for result in tree.roots:
        if result.symbol == "MAWP" and result.value is not None:
            annotations["MAWP"] = _pressure(result.value, system)
        elif result.symbol == "P_T" and result.value is not None:
            annotations["Test pressure"] = _pressure(result.value, system)
    annotations["Design pressure"] = _pressure_from_mpa(inputs.design_pressure_mpa, system)
    annotations["Design temperature"] = _temperature(inputs.design_temperature_c, system)
    annotations["Corrosion allowance"] = _length(inputs.corrosion_allowance_mm, system)
    if inputs.provided_shell_thickness_mm is not None:
        annotations["Shell plate"] = _length(inputs.provided_shell_thickness_mm, system)

    return VesselGA(
        tag=inputs.tag,
        inside_diameter_mm=inputs.inside_diameter_mm,
        tangent_to_tangent_mm=inputs.tangent_to_tangent_mm,
        shell_thickness_mm=provided_or_required_shell_mm(inputs, tree),
        head_type=inputs.head_type,
        unit_system=system,
        annotations=annotations,
        orientation=inputs.orientation,
        nozzles=tuple(
            NozzleGA(
                tag=nozzle.tag,
                elevation_mm=nozzle.elevation_mm,
                outside_diameter_mm=nozzle.outside_diameter_mm,
                projection_mm=nozzle.projection_mm,
                service=nozzle.service,
            )
            for nozzle in sorted(inputs.nozzles, key=lambda n: (n.elevation_mm, n.tag))
        ),
        skirt_height_mm=(
            inputs.support_height_mm
            if inputs.support_type == "skirt" and inputs.orientation == "vertical"
            else 0.0
        ),
    )


def _pressure(pa: float, system: UnitSystem) -> str:
    return format_value(from_base(pa, "pressure", system), display_unit("pressure", system))


def _pressure_from_mpa(mpa: float, system: UnitSystem) -> str:
    return _pressure(mpa * 1.0e6, system)


def _length(mm_value: float, system: UnitSystem) -> str:
    return format_value(from_base(mm_value / 1000.0, "length", system), display_unit("length", system))


def _temperature(celsius: float, system: UnitSystem) -> str:
    return format_value(from_base(celsius, "temperature", system), display_unit("temperature", system))


def _screen(ga: VesselGA, x: float, y: float) -> tuple[float, float]:
    """Map a vessel-frame point to the sheet.

    A horizontal vessel is drawn with its axis along the sheet's X: the frame
    is transposed so the same GA code serves both orientations, and the 3D
    preview and the 2D drawing stay one parameter set apart (FR-3D, D3).
    """
    if ga.orientation == "horizontal":
        return y, x
    return x, y


def _head_polyline(ga: VesselGA, *, top: bool) -> list[tuple[float, float]]:
    """Points of a head outline; *top* bulges up at y=L, else down at y=0."""
    radius = ga.outside_radius_mm
    depth = ga.head_depth_mm
    points: list[tuple[float, float]] = []
    for step in range(33):
        theta = math.pi * step / 32
        x = radius * math.cos(theta)
        y = depth * math.sin(theta)
        if top:
            points.append((x, ga.tangent_to_tangent_mm + y))
        else:
            points.append((-x, -y))
    return points


def write_dxf(
    ga: VesselGA,
    path: str | Path,
    *,
    project: str = "",
    drawing_no: str = "",
    date: str = "",
    drawn_by: str = "",
    checked_by: str = "",
) -> Path:
    """Write the GA sketch as a DXF file and return its path."""
    import ezdxf

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = ezdxf.new("R2010", setup=True)
    layers = {
        "GEOMETRY": 7,
        "DIMENSIONS": 3,
        "ANNOTATION": 2,
        "CENTERLINE": 1,
        "TITLEBLOCK": 7,
        "HATCH": 8,
    }
    for name, color in layers.items():
        doc.layers.add(name, color=color)
    msp = doc.modelspace()

    radius = ga.outside_radius_mm
    length = ga.tangent_to_tangent_mm
    depth = ga.head_depth_mm
    bottom = ga.bottom_offset_mm
    overhang = SKIRT_BASE_OVERHANG_MM

    def px(x: float, y: float) -> tuple[float, float]:
        return _screen(ga, x, y)

    shell = [px(-radius, 0.0), px(-radius, length), px(radius, length), px(radius, 0.0)]
    msp.add_lwpolyline(shell, close=True, dxfattribs={"layer": "GEOMETRY"})
    msp.add_lwpolyline(
        [px(x, y) for x, y in _head_polyline(ga, top=True)], dxfattribs={"layer": "GEOMETRY"}
    )
    msp.add_lwpolyline(
        [px(x, y) for x, y in _head_polyline(ga, top=False)], dxfattribs={"layer": "GEOMETRY"}
    )
    if ga.skirt_height_mm > 0:
        base = -depth - ga.skirt_height_mm
        msp.add_lwpolyline(
            [px(-radius, base), px(-radius, -depth)], dxfattribs={"layer": "GEOMETRY"}
        )
        msp.add_lwpolyline(
            [px(radius, -depth), px(radius, base)], dxfattribs={"layer": "GEOMETRY"}
        )
        msp.add_line(
            px(-radius - overhang, base), px(radius + overhang, base),
            dxfattribs={"layer": "GEOMETRY"},
        )
    for nozzle in ga.nozzles:
        y = nozzle.elevation_mm
        half = nozzle.outside_diameter_mm / 2.0
        x1 = radius
        x2 = radius + nozzle.projection_mm
        stub = [(x1, y - half), (x1, y + half), (x2, y + half), (x2, y - half)]
        msp.add_lwpolyline(
            [px(x, y) for x, y in stub],
            close=True,
            dxfattribs={"layer": "GEOMETRY"},
        )
        msp.add_line(px(x1, y), px(x2, y), dxfattribs={"layer": "CENTERLINE", "linetype": "CENTER"})
        label = f"{nozzle.tag}" + (f" {nozzle.service}" if nozzle.service else "")
        msp.add_text(
            label, dxfattribs={"layer": "ANNOTATION", "height": 14}
        ).set_placement(px(x2 + 10, y - 10))
        msp.add_line(px(x2 + 2, y), px(x2 + 10, y), dxfattribs={"layer": "ANNOTATION"})

    center_height = length + depth
    msp.add_line(
        px(0, -bottom - 40),
        px(0, center_height + 40),
        dxfattribs={"layer": "CENTERLINE", "linetype": "CENTER"},
    )

    _dxf_dimension(msp, ga, radius, length)

    origin_x = _annotation_column_x(ga)
    ann_top = ga.outside_radius_mm if ga.orientation == "horizontal" else length
    for index, (label, value) in enumerate(ga.annotations.items()):
        msp.add_text(
            f"{label}: {value}",
            dxfattribs={"layer": "ANNOTATION", "height": 18},
        ).set_placement((origin_x, ann_top - index * 26))

    _dxf_titleblock(
        msp,
        origin_x,
        ga,
        project=project,
        drawing_no=drawing_no,
        date=date,
        drawn_by=drawn_by,
        checked_by=checked_by,
    )
    doc.saveas(out)
    return out


def _annotation_column_x(ga: VesselGA) -> float:
    """Sheet x of the annotation/title-block column, clear of the geometry."""
    if ga.orientation == "horizontal":
        return ga.tangent_to_tangent_mm + 2.0 * ga.head_depth_mm + 120.0
    return ga.outside_radius_mm + 80.0


def _dim(ga: VesselGA, value_mm: float, suffix: str) -> str:
    shown = from_base(value_mm / 1000.0, "length", ga.unit_system)
    return f"{shown:.4g} {display_unit('length', ga.unit_system)}{suffix}"


def _dxf_dimension(msp, ga: VesselGA, radius: float, length: float) -> None:
    bottom = ga.bottom_offset_mm

    def px(x: float, y: float) -> tuple[float, float]:
        return _screen(ga, x, y)

    y_dim = -bottom - 60
    msp.add_line(px(-radius, -bottom - 20), px(-radius, y_dim), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_line(px(radius, -bottom - 20), px(radius, y_dim), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_line(px(-radius, y_dim), px(radius, y_dim), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_text(
        _dim(ga, ga.inside_diameter_mm, " ID"),
        dxfattribs={"layer": "DIMENSIONS", "height": 16},
    ).set_placement(px(0.0, y_dim - 30))

    x_dim = radius + 45
    msp.add_line(px(radius, 0), px(x_dim, 0), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_line(px(radius, length), px(x_dim, length), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_line(px(x_dim, 0), px(x_dim, length), dxfattribs={"layer": "DIMENSIONS"})
    msp.add_text(
        _dim(ga, ga.tangent_to_tangent_mm, " T/T"),
        dxfattribs={"layer": "DIMENSIONS", "height": 16},
    ).set_placement(px(x_dim + 10, length / 2))


def _dxf_titleblock(
    msp,
    origin_x: float,
    ga: VesselGA,
    *,
    project: str,
    drawing_no: str,
    date: str,
    drawn_by: str,
    checked_by: str,
) -> None:
    width, height = 200.0, 150.0
    if ga.orientation == "horizontal":
        y0 = -ga.outside_radius_mm - 150
    else:
        y0 = -ga.bottom_offset_mm - 150
    msp.add_lwpolyline(
        [(origin_x, y0), (origin_x + width, y0), (origin_x + width, y0 + height), (origin_x, y0 + height)],
        close=True,
        dxfattribs={"layer": "TITLEBLOCK"},
    )
    lines = [
        f"PROJECT: {project or '-'}",
        f"TAG: {ga.tag}",
        "REV: 0",
        "SCALE: NTS",
        f"UNITS: {ga.unit_system.value}",
        f"DWG: {drawing_no or 'GA-001'}",
        f"DATE: {date or '-'}",
        f"DRAWN: {drawn_by or '-'}",
        f"CHECKED: {checked_by or '-'}",
        "NOT FOR CONSTRUCTION",
    ]
    for index, text in enumerate(lines):
        msp.add_text(text, dxfattribs={"layer": "TITLEBLOCK", "height": 14}).set_placement(
            (origin_x + 8, y0 + height - 20 - index * 16)
        )


def write_pdf(
    ga: VesselGA,
    path: str | Path,
    *,
    project: str = "",
    drawing_no: str = "",
    date: str = "",
    drawn_by: str = "",
    checked_by: str = "",
) -> Path:
    """Write the GA sketch as a print-ready PDF and return its path."""
    from reportlab.lib.pagesizes import (
        A3,
        landscape,
    )
    from reportlab.lib.units import (
        mm,
    )
    from reportlab.pdfgen import (
        canvas,
    )

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    page_w, page_h = landscape(A3)
    pdf = canvas.Canvas(str(out), pagesize=(page_w, page_h))
    pdf.setTitle(f"{ga.tag} GA drawing")

    radius = ga.outside_radius_mm
    length = ga.tangent_to_tangent_mm
    depth = ga.head_depth_mm
    overhang = SKIRT_BASE_OVERHANG_MM
    margin = 45 * mm

    def px(x: float, y: float) -> tuple[float, float]:
        return _screen(ga, x, y)

    # Frame the sheet from the projected geometry so both orientations fit.
    frame = [px(-radius, 0.0), px(-radius, length), px(radius, length), px(radius, 0.0)]
    frame += [px(x, y) for x, y in _head_polyline(ga, top=True)]
    frame += [px(x, y) for x, y in _head_polyline(ga, top=False)]
    if ga.skirt_height_mm > 0:
        base = -depth - ga.skirt_height_mm
        frame += [px(-radius, base), px(radius, base), px(-radius - overhang, base), px(radius + overhang, base)]
    for nozzle in ga.nozzles:
        y = nozzle.elevation_mm
        half = nozzle.outside_diameter_mm / 2.0
        frame += [px(radius, y - half), px(radius + nozzle.projection_mm, y + half)]
    xs = [x for x, _y in frame]
    ys = [y for _x, y in frame]
    total_width = max(xs) - min(xs) + 60
    total_height = max(ys) - min(ys) + 60
    scale = min(
        (page_w - 2 * margin) / max(total_width, 1.0) / mm,
        (page_h - 2 * margin) / max(total_height, 1.0) / mm,
    )
    scale *= 0.65
    origin_x = page_w / 2 - (max(xs) + min(xs)) / 2.0 * mm * scale
    origin_y = margin - min(ys) * mm * scale

    def to_page(x_mm: float, y_mm: float) -> tuple[float, float]:
        return origin_x + x_mm * mm * scale, origin_y + y_mm * mm * scale

    pdf.setLineWidth(0.9)
    corners = [
        (-radius, 0.0),
        (-radius, length),
        (radius, length),
        (radius, 0.0),
    ]
    body = pdf.beginPath()
    body.moveTo(*to_page(*px(*corners[0])))
    for point in corners[1:]:
        body.lineTo(*to_page(*px(*point)))
    body.close()
    pdf.drawPath(body)

    for top in (True, False):
        points = _head_polyline(ga, top=top)
        head_path = pdf.beginPath()
        head_path.moveTo(*to_page(*px(*points[0])))
        for point in points[1:]:
            head_path.lineTo(*to_page(*px(*point)))
        pdf.drawPath(head_path)

    if ga.skirt_height_mm > 0:
        base = -depth - ga.skirt_height_mm
        pdf.setLineWidth(0.7)
        pdf.line(*to_page(*px(-radius, base)), *to_page(*px(-radius, -depth)))
        pdf.line(*to_page(*px(radius, -depth)), *to_page(*px(radius, base)))
        pdf.line(*to_page(*px(-radius - overhang, base)), *to_page(*px(radius + overhang, base)))

    pdf.setLineWidth(0.6)
    for nozzle in ga.nozzles:
        y = nozzle.elevation_mm
        half = nozzle.outside_diameter_mm / 2.0
        x1 = radius
        x2 = radius + nozzle.projection_mm
        corner_a = px(x1, y - half)
        corner_b = px(x2, y + half)
        rect_width = abs(corner_b[0] - corner_a[0]) or abs(corner_b[1] - corner_a[1])
        rect_height = abs(corner_b[1] - corner_a[1]) or abs(corner_b[0] - corner_a[0])
        pdf.rect(
            to_page(*corner_a)[0],
            to_page(*corner_a)[1],
            rect_width * mm * scale,
            rect_height * mm * scale,
        )
        label = f"{nozzle.tag}" + (f" {nozzle.service}" if nozzle.service else "")
        pdf.setFont("Helvetica", 7)
        pdf.drawString(*to_page(*px(x2 + 12, y - 10)), label)

    pdf.setDash(6, 3)
    pdf.setStrokeColorRGB(1, 0, 0)
    pdf.line(
        *to_page(*px(0.0, -ga.bottom_offset_mm - 30)),
        *to_page(*px(0.0, length + depth + 30)),
    )
    pdf.setDash()

    pdf.setFillColorRGB(0, 0, 0)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin, page_h - margin, f"{ga.tag} — general arrangement")
    pdf.setFont("Helvetica", 9)
    if project:
        pdf.drawString(margin, page_h - margin + 14, f"Project: {project}")
    y = page_h - margin - 20
    for label, value in ga.annotations.items():
        pdf.drawString(margin, y, f"{label}: {value}")
        y -= 13
    pdf.setFont("Helvetica", 8)
    pdf.drawString(
        margin,
        margin / 2,
        f"Drawing {drawing_no or 'GA-001'} — date {date or '-'}; drawn {drawn_by or '-'}; "
        f"checked {checked_by or '-'}. Units: {ga.unit_system.value}. Not for construction.",
    )
    pdf.showPage()
    pdf.save()
    return out
