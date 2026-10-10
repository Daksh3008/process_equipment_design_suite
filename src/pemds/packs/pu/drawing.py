"""Pump GA sketch — pump + driver + baseplate (PU-15, DR-1..DR-5).

``pump_ga_from`` returns an :class:`ezdxf.document.Drawing` holding a simplified
elevation and plan of the pump, driver and baseplate, with nozzle callouts, the
foundation/anchor-bolt pattern, key dimensions, an annotation column and a title
block. :func:`write_dxf` saves the drawing and :func:`write_pdf` renders it to a
print-ready PDF with reportlab. Geometry is parametric and derived from the same
inputs and results as the calculation; annotations use SI display units.
"""

from __future__ import annotations

from pathlib import Path

from ...core.result import ResultTree
from ...core.units import UnitSystem, display_unit, format_value, from_base
from .model import PumpInputs

_LAYERS = {
    "GEOMETRY": 7,
    "DIMENSIONS": 3,
    "ANNOTATION": 2,
    "CENTERLINE": 1,
    "TITLEBLOCK": 7,
    "HATCH": 8,
}


def _result_text(tree: ResultTree, symbol: str) -> str:
    for result in tree.flatten():
        if result.symbol == symbol and result.value is not None:
            if result.kind == "dimensionless":
                return format_value(result.value, result.unit)
            shown = from_base(result.value, result.kind, UnitSystem.SI)
            return format_value(shown, display_unit(result.kind, UnitSystem.SI))
    return "-"


def _sub(tree: ResultTree, symbol: str, key: str) -> str:
    for result in tree.flatten():
        if result.symbol == symbol:
            return result.substitutions.get(key, "-")
    return "-"


def _motor_kw(tree: ResultTree) -> float:
    for result in tree.flatten():
        if result.symbol == "P_motor" and result.value is not None:
            return result.value / 1000.0
    return 0.0


def pump_ga_from(inputs: PumpInputs, tree: ResultTree, system: UnitSystem = UnitSystem.SI):
    """Build the pump GA as an ezdxf drawing and return it."""
    import ezdxf

    motor_kw = _motor_kw(tree)
    volute_r = max(120.0, inputs.casing_inside_radius_mm * 1.4)
    baseplate_thk = 60.0
    pedestal_h = 200.0
    driver_h = min(500.0, max(250.0, 220.0 + motor_kw * 4.0))
    driver_len = min(700.0, max(320.0, 300.0 + motor_kw * 10.0))
    pump_len = 2.0 * volute_r + 160.0
    pump_center_x = 120.0 + pump_len / 2.0
    driver_x0 = pump_center_x + volute_r + 150.0
    driver_x1 = driver_x0 + driver_len
    baseplate_len = driver_x1 + 220.0
    baseplate_width = 2.0 * volute_r + 360.0
    nozzle_w = max(80.0, inputs.loads[0].size_mm if inputs.loads else 100.0)

    doc = ezdxf.new("R2010", setup=True)
    for name, color in _LAYERS.items():
        doc.layers.add(name, color=color)
    msp = doc.modelspace()

    def poly(points, layer="GEOMETRY", close=False):
        msp.add_lwpolyline(points, close=close, dxfattribs={"layer": layer})

    def line(a, b, layer="GEOMETRY"):
        msp.add_line(a, b, dxfattribs={"layer": layer})

    def text(value, x, y, height=14.0, layer="ANNOTATION"):
        msp.add_text(value, dxfattribs={"layer": layer, "height": height}).set_placement((x, y))

    # --- elevation view ---------------------------------------------------
    base_y = 0.0
    top_y = base_y + baseplate_thk
    poly([(0.0, base_y), (baseplate_len, base_y), (baseplate_len, top_y), (0.0, top_y)], close=True)
    # pump pedestal
    ped_x0 = pump_center_x - pump_len * 0.25
    poly(
        [
            (ped_x0, top_y),
            (ped_x0 + pump_len * 0.5, top_y),
            (ped_x0 + pump_len * 0.5, top_y + pedestal_h),
            (ped_x0, top_y + pedestal_h),
        ],
        close=True,
    )
    # volute casing
    volute_center = (pump_center_x, top_y + pedestal_h + volute_r)
    msp.add_circle(volute_center, volute_r, dxfattribs={"layer": "GEOMETRY"})
    msp.add_circle(volute_center, volute_r * 0.35, dxfattribs={"layer": "GEOMETRY"})
    # suction nozzle (horizontal, left)
    poly(
        [
            (volute_center[0] - volute_r - 130.0, volute_center[1] - nozzle_w / 2.0),
            (volute_center[0] - volute_r, volute_center[1] - nozzle_w / 2.0),
            (volute_center[0] - volute_r, volute_center[1] + nozzle_w / 2.0),
            (volute_center[0] - volute_r - 130.0, volute_center[1] + nozzle_w / 2.0),
        ],
        close=True,
    )
    # discharge nozzle (vertical, up)
    poly(
        [
            (volute_center[0] - nozzle_w / 2.0, volute_center[1] + volute_r),
            (volute_center[0] + nozzle_w / 2.0, volute_center[1] + volute_r),
            (volute_center[0] + nozzle_w / 2.0, volute_center[1] + volute_r + 150.0),
            (volute_center[0] - nozzle_w / 2.0, volute_center[1] + volute_r + 150.0),
        ],
        close=True,
    )
    # driver and coupling
    driver_y0 = top_y + pedestal_h
    poly(
        [
            (driver_x0, driver_y0),
            (driver_x1, driver_y0),
            (driver_x1, driver_y0 + driver_h),
            (driver_x0, driver_y0 + driver_h),
        ],
        close=True,
    )
    coupling_x0 = volute_center[0] + volute_r
    poly(
        [
            (coupling_x0, volute_center[1] - 30.0),
            (driver_x0, volute_center[1] - 30.0),
            (driver_x0, volute_center[1] + 30.0),
            (coupling_x0, volute_center[1] + 30.0),
        ],
        close=True,
    )
    # shaft centreline
    line(
        (volute_center[0] - volute_r - 180.0, volute_center[1]),
        (driver_x1 + 40.0, volute_center[1]),
        layer="CENTERLINE",
    )
    text(f"suction DN{nozzle_w:g}", volute_center[0] - volute_r - 128.0, volute_center[1] + nozzle_w / 2.0 + 12.0)
    text(f"discharge DN{nozzle_w:g}", volute_center[0] + nozzle_w / 2.0 + 12.0, volute_center[1] + volute_r + 130.0)
    text(f"pump {inputs.tag}", pump_center_x - 60.0, top_y + pedestal_h + 2.0 * volute_r + 20.0)
    text("driver", driver_x0 + driver_len / 2.0 - 30.0, driver_y0 + driver_h + 16.0)

    # --- plan view (below the elevation) ----------------------------------
    plan_top = -(2.0 * volute_r + 260.0)
    plan_bottom = plan_top - baseplate_width
    poly(
        [(0.0, plan_top), (baseplate_len, plan_top), (baseplate_len, plan_bottom), (0.0, plan_bottom)],
        close=True,
    )
    pump_top = plan_top - (baseplate_width - 2.0 * volute_r) / 2.0
    pump_bottom = pump_top - 2.0 * volute_r
    poly(
        [
            (pump_center_x - volute_r, pump_top),
            (pump_center_x + volute_r, pump_top),
            (pump_center_x + volute_r, pump_bottom),
            (pump_center_x - volute_r, pump_bottom),
        ],
        close=True,
    )
    plan_driver_top = plan_top - (baseplate_width - 2.0 * volute_r * 0.7) / 2.0
    plan_driver_bottom = plan_driver_top - 2.0 * volute_r * 0.7
    poly(
        [
            (driver_x0, plan_driver_top),
            (driver_x1, plan_driver_top),
            (driver_x1, plan_driver_bottom),
            (driver_x0, plan_driver_bottom),
        ],
        close=True,
    )
    line((pump_center_x, plan_top - 20.0), (pump_center_x, plan_bottom + 20.0), layer="CENTERLINE")
    line((0.0, (plan_top + plan_bottom) / 2.0), (baseplate_len, (plan_top + plan_bottom) / 2.0), layer="CENTERLINE")

    # anchor-bolt pattern (four corner bolts + cross marks)
    inset = 90.0
    for bx, by in (
        (inset, plan_top - inset),
        (baseplate_len - inset, plan_top - inset),
        (baseplate_len - inset, plan_bottom + inset),
        (inset, plan_bottom + inset),
    ):
        msp.add_circle((bx, by), 22.0, dxfattribs={"layer": "GEOMETRY"})
        line((bx - 30.0, by), (bx + 30.0, by), layer="CENTERLINE")
        line((bx, by - 30.0), (bx, by + 30.0), layer="CENTERLINE")
    text(
        f"foundation / anchor-bolt pattern ({4} x M24 typical) - {system.value} units",
        40.0,
        plan_bottom - 40.0,
    )

    # --- dimensions -------------------------------------------------------
    line((0.0, plan_bottom - 70.0), (baseplate_len, plan_bottom - 70.0), layer="DIMENSIONS")
    line((0.0, plan_bottom - 40.0), (0.0, plan_bottom - 90.0), layer="DIMENSIONS")
    line((baseplate_len, plan_bottom - 40.0), (baseplate_len, plan_bottom - 90.0), layer="DIMENSIONS")
    text(
        f"baseplate length {baseplate_len:.0f} mm",
        baseplate_len / 2.0 - 70.0,
        plan_bottom - 100.0,
        layer="DIMENSIONS",
    )
    text(
        f"baseplate width {baseplate_width:.0f} mm",
        baseplate_len + 28.0,
        (plan_top + plan_bottom) / 2.0,
        layer="DIMENSIONS",
    )

    # --- annotation column and title block --------------------------------
    column_x = baseplate_len + 200.0
    annotations = [
        ("Tag", inputs.tag),
        ("Service", inputs.service),
        ("Flow", f"{inputs.flow_m3_h:g} m^3/h"),
        ("Head", f"{inputs.head_m:g} m"),
        ("Selected model", _sub(tree, "selection", "model")),
        ("Duty efficiency", _sub(tree, "selection", "duty efficiency")),
        ("NPSHa", _result_text(tree, "NPSHa")),
        ("Driver", _result_text(tree, "P_motor")),
        ("Casing MAWP", _result_text(tree, "P_casing")),
        ("Casing test", _result_text(tree, "P_T")),
        ("Seal plan", _sub(tree, "seal_arrangement", "flush plan")),
        ("Vibration", _result_text(tree, "v_rms")),
    ]
    for index, (label, value) in enumerate(annotations):
        text(f"{label}: {value}", column_x, volute_center[1] + volute_r + 60.0 - index * 30.0, height=16.0)

    _titleblock(msp, column_x, plan_bottom, inputs)

    return doc


def _titleblock(msp, x0: float, y0: float, inputs: PumpInputs) -> None:
    width, height = 320.0, 180.0
    top = y0 + height
    msp.add_lwpolyline(
        [(x0, y0), (x0 + width, y0), (x0 + width, top), (x0, top)],
        close=True,
        dxfattribs={"layer": "TITLEBLOCK"},
    )
    lines = [
        "PUMP GENERAL ARRANGEMENT",
        f"TAG: {inputs.tag}",
        "REV: 0",
        "SCALE: NTS",
        "UNITS: SI",
        "DWG: GA-PU-001",
        "NOT FOR CONSTRUCTION",
    ]
    for index, value in enumerate(lines):
        msp.add_text(value, dxfattribs={"layer": "TITLEBLOCK", "height": 16.0}).set_placement(
            (x0 + 10.0, top - 24.0 - index * 22.0)
        )


def write_dxf(drawing, path: str | Path) -> Path:
    """Save an ezdxf drawing to *path* and return the path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    drawing.saveas(out)
    return out


def _entity_geometry(drawing):
    """Extract lines, polylines, circles and text from modelspace."""
    lines: list[tuple[tuple[float, float], tuple[float, float]]] = []
    polylines: list[tuple[list[tuple[float, float]], bool]] = []
    circles: list[tuple[tuple[float, float], float]] = []
    texts: list[tuple[tuple[float, float], str, float]] = []
    for entity in drawing.modelspace():
        kind = entity.dxftype()
        if kind == "LINE":
            lines.append(
                (
                    (entity.dxf.start.x, entity.dxf.start.y),
                    (entity.dxf.end.x, entity.dxf.end.y),
                )
            )
        elif kind == "LWPOLYLINE":
            points = [(p[0], p[1]) for p in entity.get_points()]
            polylines.append((points, bool(entity.closed)))
        elif kind == "CIRCLE":
            circles.append(((entity.dxf.center.x, entity.dxf.center.y), entity.dxf.radius))
        elif kind == "TEXT":
            insert = entity.dxf.insert
            texts.append(((insert.x, insert.y), str(entity.dxf.text), float(entity.dxf.height)))
    return lines, polylines, circles, texts


def write_pdf(drawing, path: str | Path) -> Path:
    """Render a pump GA drawing to a print-ready PDF and return the path."""
    from reportlab.lib.pagesizes import (
        A3,
        landscape,
    )
    from reportlab.pdfgen import (
        canvas,
    )

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    page_w, page_h = landscape(A3)
    margin = 24.0
    lines, polylines, circles, texts = _entity_geometry(drawing)

    xs: list[float] = []
    ys: list[float] = []
    for (ax, ay), (bx, by) in lines:
        xs.extend((ax, bx))
        ys.extend((ay, by))
    for points, _closed in polylines:
        with_text = list(points)
        xs.extend(p[0] for p in with_text)
        ys.extend(p[1] for p in with_text)
    for (cx, cy), radius in circles:
        xs.extend((cx - radius, cx + radius))
        ys.extend((cy - radius, cy + radius))
    for (tx, ty), _value, _height in texts:
        xs.append(tx)
        ys.append(ty)
    if not xs or not ys:
        raise ValueError("drawing has no entities to render")
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    scale = min((page_w - 2 * margin) / (max_x - min_x), (page_h - 2 * margin) / (max_y - min_y))

    def to_page(x: float, y: float) -> tuple[float, float]:
        return margin + (x - min_x) * scale, margin + (y - min_y) * scale

    pdf = canvas.Canvas(str(out), pagesize=(page_w, page_h))
    pdf.setTitle("Pump GA drawing")
    pdf.setLineWidth(0.7)
    for (ax, ay), (bx, by) in lines:
        pdf.line(*to_page(ax, ay), *to_page(bx, by))
    for points, closed in polylines:
        if len(points) < 2:
            continue
        path_obj = pdf.beginPath()
        path_obj.moveTo(*to_page(*points[0]))
        for point in points[1:]:
            path_obj.lineTo(*to_page(*point))
        if closed:
            path_obj.close()
        pdf.drawPath(path_obj)
    for (cx, cy), radius in circles:
        pdf.circle(*to_page(cx, cy), radius * scale)
    pdf.setFont("Helvetica", 6)
    for (tx, ty), value, height in texts:
        font_size = max(4.0, min(10.0, height * scale))
        pdf.setFont("Helvetica", font_size)
        pdf.drawString(*to_page(tx, ty), value)
    pdf.showPage()
    pdf.save()
    return out
