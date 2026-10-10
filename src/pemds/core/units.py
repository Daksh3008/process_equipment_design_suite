"""Unit handling for PEMDS.

Internal computation is performed in SI base units. Quantities enter through
:func:`to_base` and leave through :func:`from_base`; the calculation modules
themselves operate on plain floats so that the hot recalc path allocates no
unit objects (NFR-1).

Internal base units
--------------------
===========  ==========================
kind         base unit
===========  ==========================
length       metre (m)
pressure     pascal (Pa)
stress       pascal (Pa)
force        newton (N)
mass         kilogram (kg)
area         square metre (m^2)
volume       cubic metre (m^3)
temperature  degree Celsius (degC)
density      kilogram / cubic metre
angle        degree
time         second
power        watt
moment       newton metre
velocity     metre / second
===========  ==========================

``degC`` is retained for temperature (rather than kelvin) so that allowable
stress tables, which are published against Celsius, are consumed without an
offset conversion in the calculation path. It is an SI-accepted scale and the
offset is applied at the display boundary by :mod:`pint`.
"""

from __future__ import annotations

import math
from enum import Enum

import pint

ureg: pint.UnitRegistry = pint.UnitRegistry()
Quantity = ureg.Quantity


class UnitSystem(str, Enum):
    """Display unit system selected by the user (IN-3)."""

    SI = "SI"
    IMPERIAL = "IMPERIAL"
    MIXED = "MIXED"


BASE_UNIT: dict[str, str] = {
    "length": "meter",
    "pressure": "pascal",
    "stress": "pascal",
    "force": "newton",
    "mass": "kilogram",
    "area": "m**2",
    "volume": "m**3",
    "temperature": "degC",
    "density": "kg/m**3",
    "angle": "degree",
    "time": "second",
    "power": "watt",
    "moment": "N*m",
    "torque": "N*m",
    "velocity": "m/s",
    "flow": "m**3/s",
    "angular_speed": "rad/s",
    "viscosity": "Pa*s",
    "thermal_conductivity": "W/(m*K)",
    "specific_heat": "J/(kg*K)",
    "molar_mass": "g/mol",
    "dimensionless": "dimensionless",
    "inertia": "m**4",
}

DISPLAY_UNIT: dict[str, dict[UnitSystem, str]] = {
    "length": {UnitSystem.SI: "mm", UnitSystem.IMPERIAL: "in", UnitSystem.MIXED: "mm"},
    "pressure": {UnitSystem.SI: "MPa", UnitSystem.IMPERIAL: "psi", UnitSystem.MIXED: "bar"},
    "stress": {UnitSystem.SI: "MPa", UnitSystem.IMPERIAL: "ksi", UnitSystem.MIXED: "MPa"},
    "force": {UnitSystem.SI: "N", UnitSystem.IMPERIAL: "lbf", UnitSystem.MIXED: "N"},
    "mass": {UnitSystem.SI: "kg", UnitSystem.IMPERIAL: "lb", UnitSystem.MIXED: "kg"},
    "area": {UnitSystem.SI: "mm**2", UnitSystem.IMPERIAL: "in**2", UnitSystem.MIXED: "mm**2"},
    "volume": {UnitSystem.SI: "m**3", UnitSystem.IMPERIAL: "ft**3", UnitSystem.MIXED: "m**3"},
    "temperature": {UnitSystem.SI: "degC", UnitSystem.IMPERIAL: "degF", UnitSystem.MIXED: "degC"},
    "density": {UnitSystem.SI: "kg/m**3", UnitSystem.IMPERIAL: "lb/ft**3", UnitSystem.MIXED: "kg/m**3"},
    "angle": {UnitSystem.SI: "degree", UnitSystem.IMPERIAL: "degree", UnitSystem.MIXED: "degree"},
    "time": {UnitSystem.SI: "s", UnitSystem.IMPERIAL: "s", UnitSystem.MIXED: "s"},
    "power": {UnitSystem.SI: "kW", UnitSystem.IMPERIAL: "hp", UnitSystem.MIXED: "kW"},
    "moment": {UnitSystem.SI: "N*m", UnitSystem.IMPERIAL: "lbf*ft", UnitSystem.MIXED: "N*m"},
    "torque": {UnitSystem.SI: "N*m", UnitSystem.IMPERIAL: "lbf*ft", UnitSystem.MIXED: "N*m"},
    "velocity": {UnitSystem.SI: "m/s", UnitSystem.IMPERIAL: "ft/s", UnitSystem.MIXED: "m/s"},
    "flow": {UnitSystem.SI: "m**3/s", UnitSystem.IMPERIAL: "ft**3/s", UnitSystem.MIXED: "m**3/h"},
    "angular_speed": {UnitSystem.SI: "rad/s", UnitSystem.IMPERIAL: "rpm", UnitSystem.MIXED: "rpm"},
    "viscosity": {UnitSystem.SI: "Pa*s", UnitSystem.IMPERIAL: "cP", UnitSystem.MIXED: "cP"},
    "thermal_conductivity": {
        UnitSystem.SI: "W/(m*K)",
        UnitSystem.IMPERIAL: "Btu/(h*ft*degF)",
        UnitSystem.MIXED: "W/(m*K)",
    },
    "specific_heat": {
        UnitSystem.SI: "J/(kg*K)",
        UnitSystem.IMPERIAL: "Btu/(lb*degF)",
        UnitSystem.MIXED: "J/(kg*K)",
    },
    "molar_mass": {UnitSystem.SI: "g/mol", UnitSystem.IMPERIAL: "g/mol", UnitSystem.MIXED: "g/mol"},
    "dimensionless": {UnitSystem.SI: "", UnitSystem.IMPERIAL: "", UnitSystem.MIXED: ""},
    "inertia": {UnitSystem.SI: "m**4", UnitSystem.IMPERIAL: "in**4", UnitSystem.MIXED: "m**4"},
}


def base_unit(kind: str) -> str:
    """Return the internal SI base unit expression for *kind*."""
    try:
        return BASE_UNIT[kind]
    except KeyError as exc:  # pragma: no cover - programmer error, not user input
        raise KeyError(f"unknown quantity kind {kind!r}") from exc


def display_unit(kind: str, system: UnitSystem) -> str:
    """Return the display unit for *kind* under *system*."""
    try:
        return DISPLAY_UNIT[kind][system]
    except KeyError as exc:
        raise KeyError(f"no display unit for kind {kind!r} under {system!r}") from exc


def to_base(value: float, unit: str, kind: str) -> float:
    """Convert *value* expressed in *unit* to the internal SI base unit."""
    return float(Quantity(value, unit).to(base_unit(kind)).magnitude)


def from_base(
    value: float,
    kind: str,
    system: UnitSystem | None = None,
    unit: str | None = None,
) -> float:
    """Convert an internal SI *value* to *unit*, or to the display unit."""
    if unit is None:
        if system is None:
            raise ValueError("from_base requires either unit or system")
        unit = display_unit(kind, system)
    return float(Quantity(value, base_unit(kind)).to(unit).magnitude)


def convert(value: float, from_unit: str, to_unit: str) -> float:
    """Convert *value* between two arbitrary compatible units."""
    return float(Quantity(value, from_unit).to(to_unit).magnitude)


def format_value(value: float, unit: str, digits: int = 4) -> str:
    """Render *value* and *unit* compactly for report substitution strings."""
    if math.isnan(value) or math.isinf(value):
        return f"{value} {unit}".strip()
    magnitude = abs(value)
    if magnitude != 0 and (magnitude >= 1e6 or magnitude < 1e-3):
        return f"{value:.{digits - 1}e} {unit}".strip()
    return f"{value:.{digits}g} {unit}".strip()
