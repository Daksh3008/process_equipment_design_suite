"""VAL-2 invariant: no result under an EXPERIMENTAL result may render as verified.

Derived rows inherit the honest status of their governing entry, so a check
whose backing data is provisional can never show nested *verified* rows while
its parent admits being experimental.
"""

from __future__ import annotations

import pytest

from pemds.core.provenance import VerificationStatus
from pemds.packs.co import ColumnPack
from pemds.packs.co.model import ColumnInputs
from pemds.packs.fl import FlangePack
from pemds.packs.fl.model import FlangeInputs
from pemds.packs.hx import HeatExchangerPack
from pemds.packs.hx.model import HeatExchangerInputs
from pemds.packs.ps import PipePack
from pemds.packs.ps.model import PipeInputs
from pemds.packs.pu import PumpPack
from pemds.packs.pu.model import PumpInputs
from pemds.packs.pv import PressureVesselPack
from pemds.packs.pv.model import VesselInputs
from pemds.packs.tk import StorageTankPack
from pemds.packs.tk.model import StorageTankInputs

_CASES = [
    (PressureVesselPack(), VesselInputs(
        tag="V-1", inside_diameter_mm=2000.0, tangent_to_tangent_mm=4000.0,
        material_key="SA-516-70", head_material_key="SA-516-70",
        design_pressure_mpa=1.0, design_temperature_c=150.0)),
    (PipePack(), PipeInputs(
        tag="L-1", outside_diameter_mm=168.3, design_pressure_mpa=1.5,
        design_temperature_c=150.0, material_key="SA-106-B", corrosion_allowance_mm=1.0)),
    (FlangePack(), FlangeInputs(
        tag="FL-1", size="2", material_group="1.1", design_pressure_mpa=2.0,
        design_temperature_c=100.0)),
    (StorageTankPack(), StorageTankInputs(
        tag="TK-1", diameter_mm=10000.0, design_liquid_height_mm=8000.0,
        material_key="SA-516-70", design_temperature_c=60.0)),
    (HeatExchangerPack(), HeatExchangerInputs(
        tag="E-1", shell_inside_diameter_mm=800.0, shell_tangent_to_tangent_mm=3000.0,
        material_key="SA-516-70", design_pressure_mpa=1.0, design_temperature_c=150.0,
        effective_gasket_diameter_mm=850.0, tube_outside_diameter_mm=19.05,
        tube_wall_thickness_mm=2.11, tube_pitch_mm=23.8)),
    (ColumnPack(), ColumnInputs(
        tag="C-1", inside_diameter_mm=2000.0, tangent_to_tangent_mm=12000.0,
        material_key="SA-516-70", design_pressure_mpa=1.0, design_temperature_c=150.0)),
    (PumpPack(), PumpInputs(
        tag="P-1", service="water", fluid_name="water", flow_m3_h=100.0, head_m=50.0)),
]


def _assert_propagation(node) -> None:
    for child in node.children:
        if node.verification is VerificationStatus.EXPERIMENTAL:
            assert child.verification is VerificationStatus.EXPERIMENTAL, (
                f"{node.symbol} is experimental but child {child.symbol} is {child.verification.value}"
            )
        _assert_propagation(child)


@pytest.mark.parametrize(
    "pack,inputs",
    _CASES,
    ids=["pressure_vessel", "piping", "flange", "storage_tank", "heat_exchanger", "column", "pump"],
)
def test_no_verified_row_beneath_an_experimental_result(ctx, pack, inputs):
    tree = pack.calculate(inputs, ctx)
    for root in tree.roots:
        _assert_propagation(root)