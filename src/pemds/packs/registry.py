"""Pack registry (NFR-7): map an equipment family to its pack class.

New equipment packs plug in by adding one entry here; the CLI and the GUI both
resolve families through this single table, so a new pack needs no edits to
either surface. Imports are lazy so a heavyweight or optional pack is only
loaded when its family is actually used.
"""

from __future__ import annotations

import importlib

#: family key -> (module, class name)
_PACKS: dict[str, tuple[str, str]] = {
    "pressure_vessel": ("pemds.packs.pv", "PressureVesselPack"),
    "piping": ("pemds.packs.ps", "PipePack"),
    "flange": ("pemds.packs.fl", "FlangePack"),
    "storage_tank": ("pemds.packs.tk", "StorageTankPack"),
    "heat_exchanger": ("pemds.packs.hx", "HeatExchangerPack"),
    "column": ("pemds.packs.co", "ColumnPack"),
    "pump": ("pemds.packs.pu", "PumpPack"),
}


def families() -> list[str]:
    """All registered equipment families, in display order."""
    return list(_PACKS)


def get_pack_class(family: str) -> type:
    """Return the pack class for *family*, importing its module on first use."""
    try:
        module_name, class_name = _PACKS[family]
    except KeyError as exc:
        raise ValueError(
            f"unsupported equipment family {family!r}; known families: {families()}"
        ) from exc
    module = importlib.import_module(module_name)
    return getattr(module, class_name)
