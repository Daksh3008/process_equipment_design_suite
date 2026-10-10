"""Performance gates (NFR-1): live recalc, report and 3D within budget."""

from __future__ import annotations

import time

from pemds.packs.pv import PressureVesselPack
from pemds.packs.pv.model import VesselInputs
from pemds.report.engine import render_pdf

_KWARGS = {
    "tag": "V-401",
    "inside_diameter_mm": 2000.0,
    "tangent_to_tangent_mm": 6000.0,
    "material_key": "SA-516-70",
    "head_material_key": "SA-516-70",
    "design_pressure_mpa": 1.0,
    "design_temperature_c": 150.0,
    "provided_shell_thickness_mm": 16.0,
    "provided_head_thickness_mm": 16.0,
    "nozzles": [
        {
            "tag": "N1",
            "outside_diameter_mm": 219.1,
            "provided_neck_thickness_mm": 8.18,
            "projection_mm": 300.0,
            "elevation_mm": 800.0,
            "azimuth_deg": 0.0,
        },
        {
            "tag": "N2",
            "outside_diameter_mm": 168.3,
            "provided_neck_thickness_mm": 7.11,
            "projection_mm": 250.0,
            "elevation_mm": 1800.0,
            "azimuth_deg": 90.0,
        },
    ],
}


def test_live_recalc_under_100ms(ctx):
    inputs = VesselInputs(**_KWARGS)
    pack = PressureVesselPack()
    pack.calculate(inputs, ctx)  # warm the lazy imports and caches
    start = time.perf_counter()
    for _ in range(5):
        pack.calculate(inputs, ctx)
    average = (time.perf_counter() - start) / 5.0
    assert average < 0.100, f"live recalc averaged {average * 1000:.1f} ms (limit 100 ms)"


def test_report_generation_under_3s(ctx, tmp_path):
    tree = PressureVesselPack().calculate(VesselInputs(**_KWARGS), ctx)
    start = time.perf_counter()
    render_pdf(
        project_name="perf",
        equipment_id="V-401",
        family="pressure_vessel",
        inputs=VesselInputs(**_KWARGS),
        tree=tree,
        path=tmp_path / "report.pdf",
    )
    elapsed = time.perf_counter() - start
    assert elapsed < 3.0, f"report generation took {elapsed:.2f} s (limit 3 s)"
