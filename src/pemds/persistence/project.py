"""Project data model (PM-1, PM-3, PM-4).

The project is the portable unit of work. Equipment inputs are stored as plain
JSON so a project written by one version can be read by another, with
``schema_version`` guarding migration (NFR-6).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1


class EquipmentItem(BaseModel):
    """One piece of equipment in a project."""

    model_config = ConfigDict(extra="forbid")

    id: str
    family: str
    inputs: dict[str, Any]
    revision: int = 1
    label: str = ""


class Project(BaseModel):
    """A complete project."""

    model_config = ConfigDict(extra="forbid")

    name: str
    schema_version: int = Field(default=SCHEMA_VERSION)
    equipment: list[EquipmentItem] = Field(default_factory=list)
    created: str = ""
    modified: str = ""
