"""Fluid property correlations and phase determination — FR-CC (CC-2, CC-3, CC-4, CC-10).

Decision D7: property evaluation is a hybrid — the identity data lives in our own
NIST-sourced snapshot (:mod:`pemds.data.components`) while temperature-dependent
properties are evaluated with the pinned CoolProp release. Every value returned
here is a :class:`~pemds.core.result.Result` stamped with
``{source, correlation, version, evaluated-at-T}`` (CC-3) and an accuracy note
(CC-10); values are engineering estimates, not lab measurements.

CoolProp is imported lazily so the identity database and the rest of the package
stay importable without it (NFR-8). If it is missing, property evaluation raises
:class:`~pemds.data.loader.DataError` with an actionable message.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..calc.common import make_result
from ..core.calc import CodeEditions, citation_for, provable
from ..core.result import Issue, Result, Severity
from ..core.standards import COOLPROP
from ..core.units import format_value
from .components import Component, ComponentDB
from .loader import DataError

try:  # pragma: no cover - exercised by the import path, not by a test
    import CoolProp
    import CoolProp.CoolProp as _CP

    _VERSION = CoolProp.__version__
except Exception:  # noqa: BLE001 - any import failure degrades to a clear error at use
    _CP = None
    _VERSION = "unknown"


ACCURACY_NOTE = (
    "CoolProp Helmholtz-energy equation of state; typical uncertainty is well below 1 % "
    "for common fluids near ambient conditions. Consult the CoolProp fluid documentation "
    "for fluid-specific accuracy and valid ranges."
)


def _coolprop():
    if _CP is None:
        raise DataError(
            "CoolProp is required for fluid property evaluation (decision D7). "
            "Install the pinned dependency with `pip install CoolProp`."
        )
    return _CP


def _kelvin(temperature_c: float) -> float:
    return temperature_c + 273.15


def _critical_point(key: str) -> tuple[float, float]:
    cp = _coolprop()
    temperature = float(cp.PropsSI("Tcrit", "", 0, "", 0, key))
    pressure = float(cp.PropsSI("Pcrit", "", 0, "", 0, key))
    return temperature, pressure


class Phase(str, Enum):
    """Phase of a fluid at a design temperature and pressure (CC-4)."""

    LIQUID = "liquid"
    VAPOUR = "vapour"
    TWO_PHASE = "two-phase"
    SUPERCRITICAL = "supercritical"
    UNKNOWN = "unknown"


def _source_fields(temperature_c: float, pressure_pa: float | None = None) -> dict[str, str]:
    fields = {
        "source": f"CoolProp {_VERSION}",
        "evaluated at": f"{temperature_c:g} degC",
    }
    if pressure_pa is not None:
        fields["pressure"] = format_value(pressure_pa, "Pa")
    return fields


def _na_result(symbol: str, kind: str, formula: str, substitutions: dict[str, str], citation, message: str) -> Result:
    """A result that could not be evaluated, carrying the reason as an issue."""
    result = make_result(
        symbol=symbol,
        value=None,
        kind=kind,
        formula=formula,
        substitutions=substitutions,
        citation=citation,
    )
    result.issues.append(
        Issue(
            severity=Severity.WARNING,
            message=message,
            rationale="Value not available in this state; treat the property as undefined here.",
            citation=citation,
        )
    )
    return result


def _wrap(key: str, output: str, temperature_c: float, exc: Exception) -> DataError:
    return DataError(
        f"CoolProp could not evaluate {output!r} for {key!r} at {temperature_c:g} degC: {exc}"
    )


@provable(COOLPROP, "saturation vapour pressure (Helmholtz EOS)", "S22")
def saturation_pressure(fluid_key: str, temperature_c: float, editions: CodeEditions) -> Result:
    """Saturation vapour pressure at *temperature_c* (CC-2, CC-4)."""
    cp = _coolprop()
    temperature = _kelvin(temperature_c)
    critical_t, _ = _critical_point(fluid_key)
    substitutions = _source_fields(temperature_c)
    if temperature >= critical_t:
        return _na_result(
            "P_sat",
            "pressure",
            "P_sat = P(T, Q=0)",
            substitutions,
            citation_for(saturation_pressure, editions),
            f"{fluid_key} is at or above its critical temperature ({critical_t - 273.15:g} degC); "
            "no saturation pressure exists.",
        )
    try:
        value = float(cp.PropsSI("P", "T", temperature, "Q", 0, fluid_key))
    except ValueError as exc:
        raise _wrap(fluid_key, "P_sat", temperature_c, exc) from exc
    substitutions["accuracy"] = ACCURACY_NOTE
    return make_result(
        symbol="P_sat",
        value=value,
        kind="pressure",
        formula="P_sat = P(T, Q=0) [saturation]",
        substitutions=substitutions,
        citation=citation_for(saturation_pressure, editions),
        inputs_used=["fluid_key", "temperature_c"],
    )


@provable(COOLPROP, "saturated liquid density (Helmholtz EOS)", "S22")
def saturated_liquid_density(fluid_key: str, temperature_c: float, editions: CodeEditions) -> Result:
    """Density of the saturated liquid at *temperature_c*."""
    cp = _coolprop()
    temperature = _kelvin(temperature_c)
    critical_t, _ = _critical_point(fluid_key)
    substitutions = _source_fields(temperature_c)
    if temperature >= critical_t:
        return _na_result(
            "rho_L",
            "density",
            "rho_L = D(T, Q=0)",
            substitutions,
            citation_for(saturated_liquid_density, editions),
            f"No saturated liquid above the critical temperature ({critical_t - 273.15:g} degC).",
        )
    try:
        value = float(cp.PropsSI("D", "T", temperature, "Q", 0, fluid_key))
    except ValueError as exc:
        raise _wrap(fluid_key, "rho_L", temperature_c, exc) from exc
    substitutions["accuracy"] = ACCURACY_NOTE
    return make_result(
        symbol="rho_L",
        value=value,
        kind="density",
        formula="rho_L = D(T, Q=0) [saturated liquid]",
        substitutions=substitutions,
        citation=citation_for(saturated_liquid_density, editions),
        inputs_used=["fluid_key", "temperature_c"],
    )


@provable(COOLPROP, "saturated vapour density (Helmholtz EOS)", "S22")
def saturated_vapour_density(fluid_key: str, temperature_c: float, editions: CodeEditions) -> Result:
    """Density of the saturated vapour at *temperature_c*."""
    cp = _coolprop()
    temperature = _kelvin(temperature_c)
    critical_t, _ = _critical_point(fluid_key)
    substitutions = _source_fields(temperature_c)
    if temperature >= critical_t:
        return _na_result(
            "rho_V",
            "density",
            "rho_V = D(T, Q=1)",
            substitutions,
            citation_for(saturated_vapour_density, editions),
            f"No saturated vapour above the critical temperature ({critical_t - 273.15:g} degC).",
        )
    try:
        value = float(cp.PropsSI("D", "T", temperature, "Q", 1, fluid_key))
    except ValueError as exc:
        raise _wrap(fluid_key, "rho_V", temperature_c, exc) from exc
    substitutions["accuracy"] = ACCURACY_NOTE
    return make_result(
        symbol="rho_V",
        value=value,
        kind="density",
        formula="rho_V = D(T, Q=1) [saturated vapour]",
        substitutions=substitutions,
        citation=citation_for(saturated_vapour_density, editions),
        inputs_used=["fluid_key", "temperature_c"],
    )


@provable(COOLPROP, "single-phase density (Helmholtz EOS)", "S22")
def density(fluid_key: str, temperature_c: float, pressure_pa: float, editions: CodeEditions) -> Result:
    """Density at the specified temperature and pressure (single-phase)."""
    cp = _coolprop()
    temperature = _kelvin(temperature_c)
    try:
        value = float(cp.PropsSI("D", "T", temperature, "P", pressure_pa, fluid_key))
    except ValueError as exc:
        raise _wrap(fluid_key, "density", temperature_c, exc) from exc
    substitutions = _source_fields(temperature_c, pressure_pa)
    substitutions["accuracy"] = ACCURACY_NOTE
    return make_result(
        symbol="rho",
        value=value,
        kind="density",
        formula="rho = D(T, P)",
        substitutions=substitutions,
        citation=citation_for(density, editions),
        inputs_used=["fluid_key", "temperature_c", "pressure_pa"],
    )


@provable(COOLPROP, "saturated liquid dynamic viscosity (Helmholtz EOS)", "S22")
def liquid_viscosity(fluid_key: str, temperature_c: float, editions: CodeEditions) -> Result:
    """Dynamic viscosity of the saturated liquid at *temperature_c*."""
    cp = _coolprop()
    temperature = _kelvin(temperature_c)
    critical_t, _ = _critical_point(fluid_key)
    substitutions = _source_fields(temperature_c)
    if temperature >= critical_t:
        return _na_result(
            "mu_L",
            "viscosity",
            "mu_L = V(T, Q=0)",
            substitutions,
            citation_for(liquid_viscosity, editions),
            f"No saturated liquid above the critical temperature ({critical_t - 273.15:g} degC).",
        )
    try:
        value = float(cp.PropsSI("V", "T", temperature, "Q", 0, fluid_key))
    except ValueError as exc:
        raise _wrap(fluid_key, "mu_L", temperature_c, exc) from exc
    substitutions["accuracy"] = ACCURACY_NOTE
    return make_result(
        symbol="mu_L",
        value=value,
        kind="viscosity",
        formula="mu_L = V(T, Q=0) [saturated liquid]",
        substitutions=substitutions,
        citation=citation_for(liquid_viscosity, editions),
        inputs_used=["fluid_key", "temperature_c"],
    )


@provable(COOLPROP, "saturated vapour dynamic viscosity (Helmholtz EOS)", "S22")
def vapour_viscosity(fluid_key: str, temperature_c: float, editions: CodeEditions) -> Result:
    """Dynamic viscosity of the saturated vapour at *temperature_c*."""
    cp = _coolprop()
    temperature = _kelvin(temperature_c)
    critical_t, _ = _critical_point(fluid_key)
    substitutions = _source_fields(temperature_c)
    if temperature >= critical_t:
        return _na_result(
            "mu_V",
            "viscosity",
            "mu_V = V(T, Q=1)",
            substitutions,
            citation_for(vapour_viscosity, editions),
            f"No saturated vapour above the critical temperature ({critical_t - 273.15:g} degC).",
        )
    try:
        value = float(cp.PropsSI("V", "T", temperature, "Q", 1, fluid_key))
    except ValueError as exc:
        raise _wrap(fluid_key, "mu_V", temperature_c, exc) from exc
    substitutions["accuracy"] = ACCURACY_NOTE
    return make_result(
        symbol="mu_V",
        value=value,
        kind="viscosity",
        formula="mu_V = V(T, Q=1) [saturated vapour]",
        substitutions=substitutions,
        citation=citation_for(vapour_viscosity, editions),
        inputs_used=["fluid_key", "temperature_c"],
    )


@provable(COOLPROP, "isobaric specific heat (Helmholtz EOS)", "S22")
def specific_heat(fluid_key: str, temperature_c: float, pressure_pa: float, editions: CodeEditions) -> Result:
    """Isobaric specific heat at the specified temperature and pressure."""
    cp = _coolprop()
    temperature = _kelvin(temperature_c)
    try:
        value = float(cp.PropsSI("C", "T", temperature, "P", pressure_pa, fluid_key))
    except ValueError as exc:
        raise _wrap(fluid_key, "cp", temperature_c, exc) from exc
    substitutions = _source_fields(temperature_c, pressure_pa)
    substitutions["accuracy"] = ACCURACY_NOTE
    return make_result(
        symbol="cp",
        value=value,
        kind="specific_heat",
        formula="cp = C(T, P)",
        substitutions=substitutions,
        citation=citation_for(specific_heat, editions),
        inputs_used=["fluid_key", "temperature_c", "pressure_pa"],
    )


@provable(COOLPROP, "thermal conductivity (Helmholtz EOS)", "S22")
def thermal_conductivity(
    fluid_key: str, temperature_c: float, pressure_pa: float, editions: CodeEditions
) -> Result:
    """Thermal conductivity at the specified temperature and pressure."""
    cp = _coolprop()
    temperature = _kelvin(temperature_c)
    try:
        value = float(cp.PropsSI("L", "T", temperature, "P", pressure_pa, fluid_key))
    except ValueError as exc:
        raise _wrap(fluid_key, "thermal conductivity", temperature_c, exc) from exc
    substitutions = _source_fields(temperature_c, pressure_pa)
    substitutions["accuracy"] = ACCURACY_NOTE
    return make_result(
        symbol="k",
        value=value,
        kind="thermal_conductivity",
        formula="k = L(T, P)",
        substitutions=substitutions,
        citation=citation_for(thermal_conductivity, editions),
        inputs_used=["fluid_key", "temperature_c", "pressure_pa"],
    )


@provable(COOLPROP, "normal boiling point (Helmholtz EOS)", "S22")
def boiling_point(fluid_key: str, pressure_pa: float, editions: CodeEditions) -> Result:
    """Saturation temperature (degC) at *pressure_pa*.

    Pressures outside the saturation envelope ``[P_triple, P_crit]`` have no
    boiling point; the result is reported as unavailable with an issue rather
    than raising, so a design case never fails on an optional reference value.
    """
    cp = _coolprop()
    substitutions = {
        "source": f"CoolProp {_VERSION}",
        "pressure": format_value(pressure_pa, "Pa"),
    }
    substitutions["accuracy"] = ACCURACY_NOTE
    try:
        value = float(cp.PropsSI("T", "P", pressure_pa, "Q", 0, fluid_key)) - 273.15
    except ValueError:
        return _na_result(
            "T_b",
            "temperature",
            "T_b = T(P, Q=0) [saturation]",
            substitutions,
            citation_for(boiling_point, editions),
            f"{fluid_key} has no saturation temperature at {pressure_pa:g} Pa "
            "(outside the saturation envelope).",
        )
    return make_result(
        symbol="T_b",
        value=value,
        kind="temperature",
        formula="T_b = T(P, Q=0) [saturation]",
        substitutions=substitutions,
        citation=citation_for(boiling_point, editions),
        inputs_used=["fluid_key", "pressure_pa"],
    )


@provable(COOLPROP, "triple-point temperature (Helmholtz EOS)", "S22")
def freezing_point(fluid_key: str, editions: CodeEditions) -> Result:
    """Triple-point (freezing reference) temperature at one atmosphere, degC."""
    cp = _coolprop()
    try:
        value = float(cp.PropsSI("Ttriple", "", 0, "", 0, fluid_key)) - 273.15
    except ValueError as exc:
        raise DataError(f"CoolProp has no triple-point temperature for {fluid_key!r}: {exc}") from exc
    substitutions = {"source": f"CoolProp {_VERSION}"}
    substitutions["accuracy"] = ACCURACY_NOTE
    return make_result(
        symbol="T_f",
        value=value,
        kind="temperature",
        formula="T_f = T_triple",
        substitutions=substitutions,
        citation=citation_for(freezing_point, editions),
        inputs_used=["fluid_key"],
    )


@provable(COOLPROP, "critical point (Helmholtz EOS)", "S22")
def critical_point(fluid_key: str, editions: CodeEditions) -> Result:
    """Critical temperature (degC); critical pressure is reported as a substitution."""
    critical_t, critical_p = _critical_point(fluid_key)
    substitutions = {
        "source": f"CoolProp {_VERSION}",
        "P_crit": format_value(critical_p, "Pa"),
    }
    substitutions["accuracy"] = ACCURACY_NOTE
    return make_result(
        symbol="T_crit",
        value=critical_t - 273.15,
        kind="temperature",
        formula="T_crit, P_crit",
        substitutions=substitutions,
        citation=citation_for(critical_point, editions),
        inputs_used=["fluid_key"],
    )


def phase_of(fluid_key: str, temperature_c: float, pressure_pa: float) -> Phase:
    """Determine the phase at a design temperature and pressure (CC-4, pure)."""
    cp = _coolprop()
    temperature = _kelvin(temperature_c)
    critical_t, _ = _critical_point(fluid_key)
    if temperature >= critical_t:
        return Phase.SUPERCRITICAL
    try:
        saturation = float(cp.PropsSI("P", "T", temperature, "Q", 0, fluid_key))
    except ValueError:
        return Phase.UNKNOWN
    if pressure_pa > saturation * (1.0 + 1e-6):
        return Phase.LIQUID
    if pressure_pa < saturation * (1.0 - 1e-6):
        return Phase.VAPOUR
    return Phase.TWO_PHASE


@provable(COOLPROP, "phase determination", "S22")
def phase_at(fluid_key: str, temperature_c: float, pressure_pa: float, editions: CodeEditions) -> Result:
    """A report row describing the phase at a design temperature and pressure (CC-4)."""
    phase = phase_of(fluid_key, temperature_c, pressure_pa)
    substitutions = _source_fields(temperature_c, pressure_pa)
    issues: list[Issue] = []
    if phase not in (Phase.SUPERCRITICAL, Phase.UNKNOWN):
        try:
            saturation = saturation_pressure(fluid_key, temperature_c, editions)
            if saturation.value is not None:
                substitutions["P_sat"] = format_value(saturation.value, "Pa")
        except DataError as exc:
            issues.append(
                Issue(
                    severity=Severity.WARNING,
                    message=f"P_sat could not be evaluated: {exc}",
                    rationale="Optional display value; phase determination used the saturating lookups directly.",
                    citation=citation_for(phase_at, editions),
                )
            )
    result = make_result(
        symbol="phase",
        value=None,
        kind="dimensionless",
        formula=f"phase = {phase.value}",
        substitutions=substitutions,
        citation=citation_for(phase_at, editions),
        inputs_used=["fluid_key", "temperature_c", "pressure_pa"],
    )
    result.issues.extend(issues)
    return result


@dataclass(frozen=True)
class FluidDesignCase:
    """A one-click design case for a fluid at T/P (CC-3, CC-4)."""

    component: Component
    temperature_c: float
    pressure_pa: float
    phase: Phase
    properties: dict[str, Result] = field(default_factory=dict)

    def by_symbol(self) -> dict[str, Result]:
        return dict(self.properties)

    def issues(self) -> list[Issue]:
        return [issue for result in self.properties.values() for issue in result.issues]

    def design_basis(self) -> dict[str, object]:
        """The DB-3 style design-case fields (density, vapour pressure, viscosity, phase)."""

        def _value(symbol: str) -> float | None:
            result = self.properties.get(symbol)
            return result.value if result is not None else None

        return {
            "component_key": self.component.key,
            "component_name": self.component.name,
            "temperature_c": self.temperature_c,
            "pressure_pa": self.pressure_pa,
            "density_kg_m3": _value("rho") or _value("rho_L"),
            "vapour_pressure_pa": _value("P_sat"),
            "viscosity_pa_s": _value("mu_L"),
            "phase": self.phase,
        }


def design_case(
    component_key: str,
    temperature_c: float,
    pressure_pa: float,
    editions: CodeEditions,
    db: ComponentDB | None = None,
) -> FluidDesignCase:
    """Evaluate a full design case for one component at T/P (CC-3, CC-4, CC-10)."""
    database = db or ComponentDB.load_default()
    component = database.get(component_key)
    phase = phase_of(component.key, temperature_c, pressure_pa)
    properties: dict[str, Result] = {
        "rho": density(component.key, temperature_c, pressure_pa, editions),
        "P_sat": saturation_pressure(component.key, temperature_c, editions),
        "cp": specific_heat(component.key, temperature_c, pressure_pa, editions),
        "k": thermal_conductivity(component.key, temperature_c, pressure_pa, editions),
        "T_b": boiling_point(component.key, pressure_pa, editions),
        "T_f": freezing_point(component.key, editions),
    }
    if phase in (Phase.LIQUID, Phase.TWO_PHASE):
        properties["rho_L"] = saturated_liquid_density(component.key, temperature_c, editions)
        properties["mu_L"] = liquid_viscosity(component.key, temperature_c, editions)
    if phase in (Phase.VAPOUR, Phase.TWO_PHASE):
        properties["rho_V"] = saturated_vapour_density(component.key, temperature_c, editions)
        properties["mu_V"] = vapour_viscosity(component.key, temperature_c, editions)
    return FluidDesignCase(
        component=component,
        temperature_c=temperature_c,
        pressure_pa=pressure_pa,
        phase=phase,
        properties=properties,
    )
