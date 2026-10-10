"""Loader for provenance-stamped data files.

Every data file must carry a ``provenance`` header (spec section 6). A file
without one is rejected at load time — this is the runtime half of the CIT-2
copyright control.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Any

from ..core.provenance import Provenance

_REQUIRED_HEADER_KEYS = (
    "source",
    "edition",
    "clause",
    "licence",
    "transcribed_on",
    "checked_by",
)


class DataError(Exception):
    """A data file is missing, malformed, or lacks provenance."""


@dataclass(frozen=True)
class DataFile:
    """A loaded data file plus its provenance header."""

    path: str
    data: dict[str, Any]
    provenance: Provenance


def _parse_provenance(raw: object, path: str) -> Provenance:
    if not isinstance(raw, dict):
        raise DataError(f"{path}: missing 'provenance' header object")
    missing = [k for k in _REQUIRED_HEADER_KEYS if not str(raw.get(k, "")).strip()]
    if missing:
        raise DataError(f"{path}: provenance header missing required keys: {missing}")
    return Provenance(
        source=str(raw["source"]),
        edition=str(raw["edition"]),
        clause=str(raw["clause"]),
        licence=str(raw["licence"]),
        transcribed_on=str(raw["transcribed_on"]),
        checked_by=str(raw["checked_by"]),
        source_tag=str(raw["source_tag"]) if raw.get("source_tag") else None,
    )


def load_package_data(relative_path: str) -> DataFile:
    """Load a JSON data file shipped inside the ``pemds.data`` package."""
    resource = files("pemds.data").joinpath(relative_path)
    try:
        text = resource.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise DataError(f"package data file not found: {relative_path}") from exc
    return _parse(relative_path, text)


def load_path(path: str | Path) -> DataFile:
    """Load a JSON data file from the filesystem (e.g. a user-supplied table)."""
    p = Path(path)
    if not p.is_file():
        raise DataError(f"data file not found: {p}")
    return _parse(str(p), p.read_text(encoding="utf-8-sig"))


def _parse(path: str, text: str) -> DataFile:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DataError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise DataError(f"{path}: top-level JSON must be an object")
    provenance = _parse_provenance(payload.get("provenance"), path)
    return DataFile(path=path, data=payload, provenance=provenance)


def load_data_file(relative_path: str) -> DataFile:
    """Alias used by the core registry for package-relative data."""
    return load_package_data(relative_path)
