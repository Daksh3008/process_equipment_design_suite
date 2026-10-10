"""Centrifugal pump calculations — API 610 / ISO 13709 and ANSI/HI 9.6.1 (FR-PU).

Pure functions returning :class:`~pemds.core.result.Result`. Hydraulic and
mechanical relations (specific speed, hydraulic/absorbed power, casing pressure,
torque, shaft deflection and combined stress, bearing L10 life, nozzle-load
interaction, vibration margin) are evaluated from first principles and carry the
clause that defines them.

Anything that leans on the bundled *generic sample* curve catalogue (PU-3
selection, BEP, catalogue efficiency and NPSHr) or on a documented simplified
rule-of-thumb subset (type-class guidance, POR/AOR bands, mechanical-seal
selection, nozzle allowables, API 610 material class) is marked EXPERIMENTAL and
carries a warning: the sample data and the screening rules are not a substitute
for the licensed standard or vendor curves.

Specific-speed convention used throughout: ``Ns = N*sqrt(Q)/H**0.75`` with the
speed ``N`` in revolutions per minute, ``Q`` in cubic metres per second and the
head (or NPSH) in metres. Under this SI convention radial impellers fall below
about 58, mixed-flow to about 155 and axial above that.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import pairwise

from ..core.calc import CodeEditions, citation_for, citation_of, provable
from ..core.provenance import Citation, VerificationStatus
from ..core.result import Issue, Result, Severity, Verdict
from ..core.standards import (
    API_610,
    API_682,
    ASME_VIII_1,
    HI_9_6_1,
    ISO_281,
    NACE_MR0175,
)
from ..core.units import format_value
from . import shell as shell_calc
from .common import make_result, margin_verdict, require_positive

#: Standard gravity (m/s^2).
_G = 9.80665

#: ANSI/HI 9.6.1 screening NPSH margin adopted when none is supplied (m).
NPSH_MARGIN_M = 0.6

#: API 610 seal-chamber deflection limit at the seal faces (m).
SEAL_DEFLECTION_LIMIT_M = 0.05e-3

#: API 610 overall vibration velocity limit, RMS (m/s).
VIBRATION_LIMIT_M_S = 3.0e-3

#: API 610 minimum bearing L10 life at rated conditions (h).
MIN_BEARING_LIFE_H = 25000.0

#: API 610 casing hydrostatic test factor on casing MAWP.
CASING_TEST_FACTOR = 1.5

#: Standard IEC/NEMA motor ratings (kW) used to round a driver selection up.
_STANDARD_MOTOR_KW: tuple[float, ...] = (
    0.75, 1.1, 1.5, 2.2, 3.0, 4.0, 5.5, 7.5, 11.0, 15.0, 18.5, 22.0, 30.0,
    37.0, 45.0, 55.0, 75.0, 90.0, 110.0, 132.0, 160.0, 200.0, 250.0, 315.0,
    355.0, 400.0, 450.0, 500.0, 560.0, 630.0, 710.0, 800.0,
)


def _warning(citation: Citation, message: str, rationale: str) -> Issue:
    """One disclosure Issue for an experimental result (VAL-2)."""
    return Issue(
        severity=Severity.WARNING,
        message=message,
        rationale=rationale,
        citation=citation,
    )


def angular_speed_rad_s(speed_rpm: float) -> float:
    """Convert a rotational speed in rpm to angular velocity in rad/s."""
    require_positive(N=speed_rpm)
    return 2.0 * math.pi * speed_rpm / 60.0


# ---------------------------------------------------------------------------
# PU-2 — specific speed and pump type guidance
# ---------------------------------------------------------------------------


@provable(API_610, "specific speed / type classification", "S7")
def specific_speed(
    speed_rpm: float,
    flow_m3s: float,
    head_m: float,
    editions: CodeEditions,
) -> Result:
    """Specific speed ``Ns = N*sqrt(Q)/H**0.75`` (rpm, m^3/s, m)."""
    require_positive(N=speed_rpm, Q=flow_m3s, H=head_m)
    ns = speed_rpm * math.sqrt(flow_m3s) / head_m**0.75
    return make_result(
        symbol="Ns",
        value=ns,
        kind="dimensionless",
        formula="Ns = N*sqrt(Q)/H^0.75",
        substitutions={
            "N": f"{speed_rpm:.6g} rpm",
            "Q": format_value(flow_m3s, "m**3/s"),
            "H": format_value(head_m, "m"),
        },
        citation=citation_for(specific_speed, editions),
        inputs_used=["rated_speed_rpm", "flow_m3_h", "head_m"],
    )


@provable(API_610, "specific speed / type classification", "S7")
def suction_specific_speed(
    speed_rpm: float,
    flow_m3s: float,
    npsh_m: float,
    editions: CodeEditions,
) -> Result:
    """Suction specific speed ``Nss = N*sqrt(Q)/NPSH**0.75`` (rpm, m^3/s, m)."""
    require_positive(N=speed_rpm, Q=flow_m3s, NPSH=npsh_m)
    nss = speed_rpm * math.sqrt(flow_m3s) / npsh_m**0.75
    return make_result(
        symbol="Nss",
        value=nss,
        kind="dimensionless",
        formula="Nss = N*sqrt(Q)/NPSH3^0.75",
        substitutions={
            "N": f"{speed_rpm:.6g} rpm",
            "Q": format_value(flow_m3s, "m**3/s"),
            "NPSH3": format_value(npsh_m, "m"),
        },
        citation=citation_for(suction_specific_speed, editions),
        inputs_used=["rated_speed_rpm", "flow_m3_h", "npshr_m"],
    )


@provable(API_610, "specific speed / type classification", "S7",
          verification=VerificationStatus.EXPERIMENTAL)
def pump_type_classification(
    ns: float,
    nss: float,
    flow_m3s: float,
    editions: CodeEditions,
) -> Result:
    """Map Ns/Nss to an impeller family and a screening API 610 type class.

    EXPERIMENTAL: this is a rule-of-thumb mapping. API 610 selects a type class
    from a wider set of mechanical and hydraulic criteria; confirm against the
    standard and vendor data.
    """
    require_positive(Ns=ns, Nss=nss, Q=flow_m3s)
    if ns < 58.0:
        family = "radial"
        api_class = "OH (overhung, e.g. OH1/OH2)" if flow_m3s < 0.1 else "BB (between bearings, e.g. BB1/BB2)"
    elif ns < 155.0:
        family = "mixed-flow"
        api_class = "BB (between bearings, e.g. BB3/BB5) or VS for high suction energy"
    else:
        family = "axial"
        api_class = "VS (vertical suspended, e.g. VS1/VS3)"
    suction_note = (
        "high suction specific speed - review suction recirculation and NPSH margin"
        if nss > 220.0
        else "suction specific speed within the usual band"
    )
    citation = citation_for(pump_type_classification, editions)
    return make_result(
        symbol="type_class",
        value=ns,
        kind="dimensionless",
        formula="radial if Ns<58; mixed-flow if Ns<155; axial otherwise (rpm, m^3/s, m)",
        substitutions={
            "Ns": f"{ns:.4g}",
            "Nss": f"{nss:.4g}",
            "impeller family": family,
            "API 610 type class (screening)": api_class,
            "suction note": suction_note,
        },
        citation=citation,
        inputs_used=["rated_speed_rpm", "flow_m3_h", "head_m", "npshr_m"],
        verification=VerificationStatus.EXPERIMENTAL,
        issues=[
            _warning(
                citation,
                "Pump type-class guidance is a screening rule of thumb, not a "
                "standard selection.",
                "API 610 type-class selection uses a wider set of mechanical and "
                "hydraulic criteria; confirm against the standard and vendor data.",
            )
        ],
    )


# ---------------------------------------------------------------------------
# PU-3 — catalogue selection (sample data)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CurvePoint:
    """One digitised point on a pump performance curve (SI)."""

    flow_m3s: float
    head_m: float
    efficiency_pct: float
    power_kw: float
    npshr_m: float


@dataclass(frozen=True)
class PumpCurve:
    """A single-speed performance curve for one catalogue model."""

    model: str
    type_class: str
    speed_rpm: float
    points: tuple[CurvePoint, ...]

    def at(self, flow_m3s: float) -> CurvePoint | None:
        """Linearly interpolate the curve at *flow_m3s*; None if out of range."""
        points = self.points
        if flow_m3s < points[0].flow_m3s or flow_m3s > points[-1].flow_m3s:
            return None
        for left, right in pairwise(points):
            if left.flow_m3s <= flow_m3s <= right.flow_m3s:
                span = right.flow_m3s - left.flow_m3s
                if span <= 0:
                    return left
                t = (flow_m3s - left.flow_m3s) / span

                def blend(a: float, b: float, t: float = t) -> float:
                    return a + t * (b - a)

                return CurvePoint(
                    flow_m3s=flow_m3s,
                    head_m=blend(left.head_m, right.head_m),
                    efficiency_pct=blend(left.efficiency_pct, right.efficiency_pct),
                    power_kw=blend(left.power_kw, right.power_kw),
                    npshr_m=blend(left.npshr_m, right.npshr_m),
                )
        return points[-1]  # pragma: no cover - covered by the range test above

    def bep(self) -> CurvePoint:
        """The best-efficiency point of the curve."""
        return max(self.points, key=lambda point: point.efficiency_pct)


@dataclass(frozen=True)
class Candidate:
    """A catalogue curve evaluated at the duty point."""

    model: str
    type_class: str
    speed_rpm: float
    head_available_m: float
    efficiency_pct: float
    power_kw: float
    npshr_m: float
    bep_flow_m3s: float
    percent_bep: float
    head_ratio: float
    meets_head: bool


def catalogue_from_data(data: dict) -> tuple[PumpCurve, ...]:
    """Parse the sample curve catalogue payload into :class:`PumpCurve` records."""
    raw_pumps = data.get("pumps")
    if not isinstance(raw_pumps, list) or not raw_pumps:
        raise ValueError("pump catalogue must contain a non-empty 'pumps' list")
    curves: list[PumpCurve] = []
    for raw_pump in raw_pumps:
        model = str(raw_pump["model"])
        type_class = str(raw_pump["type_class"])
        for raw_curve in raw_pump.get("curves", []):
            speed = float(raw_curve["speed_rpm"])
            points = tuple(
                CurvePoint(
                    flow_m3s=float(point["flow_m3_h"]) / 3600.0,
                    head_m=float(point["head_m"]),
                    efficiency_pct=float(point["efficiency_pct"]),
                    power_kw=float(point["power_kw"]),
                    npshr_m=float(point["npshr_m"]),
                )
                for point in raw_curve["points"]
            )
            if len(points) < 2:
                raise ValueError(f"pump {model!r}: a curve needs at least two points")
            if any(b.flow_m3s <= a.flow_m3s for a, b in pairwise(points)):
                raise ValueError(f"pump {model!r}: curve flows must be strictly ascending")
            curves.append(
                PumpCurve(model=model, type_class=type_class, speed_rpm=speed, points=points)
            )
    if not curves:
        raise ValueError("pump catalogue contains no curves")
    return tuple(curves)


def rank_candidates(
    flow_m3s: float,
    head_m: float,
    catalogue: tuple[PumpCurve, ...],
    speed_rpm: float | None = None,
    speed_tolerance: float = 0.25,
) -> list[Candidate]:
    """Evaluate every catalogue curve at the duty point, best first.

    Curves whose rated speed differs from *speed_rpm* by more than
    *speed_tolerance* are skipped so an explicit duty speed constrains the
    selection. Candidates that can meet the required head rank above those that
    cannot; within each group the highest duty efficiency wins (PU-3).
    """
    require_positive(Q=flow_m3s, H=head_m)
    candidates: list[Candidate] = []
    for curve in catalogue:
        if (
            speed_rpm is not None
            and curve.speed_rpm > 0
            and abs(curve.speed_rpm - speed_rpm) / speed_rpm > speed_tolerance
        ):
            continue
        point = curve.at(flow_m3s)
        if point is None:
            continue
        bep = curve.bep()
        candidates.append(
            Candidate(
                model=curve.model,
                type_class=curve.type_class,
                speed_rpm=curve.speed_rpm,
                head_available_m=point.head_m,
                efficiency_pct=point.efficiency_pct,
                power_kw=point.power_kw,
                npshr_m=point.npshr_m,
                bep_flow_m3s=bep.flow_m3s,
                percent_bep=100.0 * flow_m3s / bep.flow_m3s,
                head_ratio=point.head_m / head_m,
                meets_head=point.head_m >= head_m,
            )
        )
    candidates.sort(key=lambda c: (not c.meets_head, -c.efficiency_pct, -c.head_ratio))
    return candidates


@provable(API_610, "catalogue selection (generic sample curves)", "S7",
          verification=VerificationStatus.EXPERIMENTAL)
def select_from_catalogue(
    flow_m3s: float,
    head_m: float,
    catalogue: tuple[PumpCurve, ...],
    editions: CodeEditions,
    speed_rpm: float | None = None,
) -> Result:
    """Rank catalogue candidates at the duty point and report the best (PU-3).

    EXPERIMENTAL: the bundled catalogue is synthetic sample data, so the
    selection, BEP and efficiency-derived figures are not verified.
    """
    require_positive(Q=flow_m3s, H=head_m)
    citation = citation_for(select_from_catalogue, editions)
    warning = _warning(
        citation,
        "Pump selection uses the bundled generic sample curves; not for "
        "production selection.",
        "Data policy: unverified catalogue data must not back a verified result.",
    )
    candidates = rank_candidates(flow_m3s, head_m, catalogue, speed_rpm)
    if not candidates:
        return make_result(
            symbol="selection",
            value=None,
            kind="dimensionless",
            formula="best match by head capability then duty efficiency",
            substitutions={"duty flow": format_value(flow_m3s, "m**3/s")},
            citation=citation,
            inputs_used=["flow_m3_h", "head_m"],
            verdict=Verdict.FAIL,
            verification=VerificationStatus.EXPERIMENTAL,
            issues=[
                warning,
                _warning(
                    citation,
                    "No catalogue curve covers the duty flow within the selected speed.",
                    "Widen the catalogue or enter a duty speed inside a model's range.",
                ),
            ],
        )
    best = candidates[0]
    runner_up = candidates[1] if len(candidates) > 1 else None
    substitutions = {
        "model": best.model,
        "type class": best.type_class,
        "speed": f"{best.speed_rpm:.6g} rpm",
        "head available": format_value(best.head_available_m, "m"),
        "head required": format_value(head_m, "m"),
        "duty efficiency": f"{best.efficiency_pct:.4g} %",
        "catalogue power": f"{best.power_kw:.4g} kW",
        "NPSHr": format_value(best.npshr_m, "m"),
        "BEP flow": format_value(best.bep_flow_m3s, "m**3/s"),
        "%BEP": f"{best.percent_bep:.4g} %",
        "candidates": str(len(candidates)),
    }
    if runner_up is not None:
        substitutions["runner-up"] = f"{runner_up.model} ({runner_up.efficiency_pct:.4g} %)"
    return make_result(
        symbol="selection",
        value=best.efficiency_pct,
        kind="dimensionless",
        formula="best = head-capable model with the highest duty efficiency",
        substitutions=substitutions,
        citation=citation,
        inputs_used=["flow_m3_h", "head_m", "rated_speed_rpm"],
        verdict=Verdict.PASS if best.meets_head else Verdict.FAIL,
        margin=best.head_ratio - 1.0,
        verification=VerificationStatus.EXPERIMENTAL,
        issues=[warning],
    )


# ---------------------------------------------------------------------------
# PU-4 — preferred / allowable operating region
# ---------------------------------------------------------------------------


@provable(API_610, "preferred and allowable operating region", "S7",
          verification=VerificationStatus.EXPERIMENTAL)
def operating_region_check(
    percent_bep: float,
    editions: CodeEditions,
    por_low: float = 70.0,
    por_high: float = 120.0,
    aor_low: float = 50.0,
    aor_high: float = 120.0,
) -> Result:
    """Check the duty point against the POR/AOR bands as a percent of BEP (PU-4).

    EXPERIMENTAL: API 610 permits a wider allowable region for stable curves; the
    bands below are a documented simplified subset and the remedy is advisory.
    """
    if not math.isfinite(percent_bep) or percent_bep < 0.0:
        raise ValueError(f"percent_bep must be finite and >= 0, got {percent_bep}")
    if not 0.0 < por_low < por_high:
        raise ValueError("preferred region bounds must satisfy 0 < low < high")
    if not 0.0 < aor_low <= por_low and aor_high >= por_high:
        raise ValueError("allowable region must enclose the preferred region")
    citation = citation_for(operating_region_check, editions)
    if por_low <= percent_bep <= por_high:
        verdict, remedy = Verdict.PASS, "operating point is inside the preferred region"
    elif aor_low <= percent_bep <= aor_high:
        verdict = Verdict.WARN
        remedy = (
            "outside the preferred region: trim the impeller, change model or use a "
            "variable-frequency drive to move the point toward BEP"
        )
    else:
        verdict = Verdict.FAIL
        remedy = (
            "outside the allowable region: select a different model or trim/speed the "
            "impeller so the duty point falls inside the allowable region"
        )
    if percent_bep < por_low:
        margin = (percent_bep - por_low) / por_low
    else:
        margin = (por_high - percent_bep) / por_high
    return make_result(
        symbol="%BEP",
        value=percent_bep,
        kind="dimensionless",
        formula="%BEP = 100 * Q_operating / Q_BEP",
        substitutions={
            "%BEP": f"{percent_bep:.4g} %",
            "preferred region": f"{por_low:.4g}-{por_high:.4g} %",
            "allowable region": f"{aor_low:.4g}-{aor_high:.4g} %",
            "remedy": remedy,
        },
        citation=citation,
        inputs_used=["flow_m3_h", "head_m"],
        verdict=verdict,
        margin=margin,
        verification=VerificationStatus.EXPERIMENTAL,
        issues=[
            _warning(
                citation,
                f"Duty point at {percent_bep:.3g} % of BEP: {remedy}.",
                "The POR/AOR bands are a simplified API 610 subset; confirm against "
                "the standard and the vendor curve.",
            )
        ],
    )


# ---------------------------------------------------------------------------
# PU-5 — NPSH
# ---------------------------------------------------------------------------


@provable(HI_9_6_1, "NPSH margin", "S9")
def npsh_check(
    npsh_available_m: float,
    npsh_required_m: float,
    editions: CodeEditions,
    margin_m: float = NPSH_MARGIN_M,
) -> Result:
    """Verify ``NPSHa >= NPSH3 + margin`` (PU-5, ANSI/HI 9.6.1)."""
    require_positive(NPSH3=npsh_required_m)
    if npsh_available_m < 0:
        raise ValueError(f"npsh_available_m must be >= 0, got {npsh_available_m}")
    if margin_m < 0:
        raise ValueError(f"margin_m must be >= 0, got {margin_m}")
    required = npsh_required_m + margin_m
    verdict, margin = margin_verdict(npsh_available_m, required)
    citation = citation_for(npsh_check, editions)
    issues: list[Issue] = []
    if verdict is Verdict.FAIL:
        issues.append(
            _warning(
                citation,
                "NPSH available is below NPSH3 plus margin: cavitation risk.",
                "Increase suction head, reduce suction losses, lower the pump or reduce "
                "speed until NPSHa >= NPSH3 + margin.",
            )
        )
    return make_result(
        symbol="NPSHa",
        value=npsh_available_m,
        kind="length",
        formula="NPSHa >= NPSH3 + margin",
        substitutions={
            "NPSHa": format_value(npsh_available_m, "m"),
            "NPSH3": format_value(npsh_required_m, "m"),
            "margin": format_value(margin_m, "m"),
            "required NPSHa": format_value(required, "m"),
        },
        citation=citation,
        inputs_used=["npsh_available_m", "npshr_m"],
        verdict=verdict,
        margin=margin,
        issues=issues,
    )


# ---------------------------------------------------------------------------
# PU-6 — power and driver sizing
# ---------------------------------------------------------------------------


@provable(API_610, "power and driver sizing", "S7")
def hydraulic_power(
    density_kg_m3: float,
    flow_m3s: float,
    head_m: float,
    editions: CodeEditions,
) -> Result:
    """Hydraulic power ``P_hyd = rho*g*Q*H`` (PU-6)."""
    require_positive(rho=density_kg_m3, Q=flow_m3s, H=head_m)
    power = density_kg_m3 * _G * flow_m3s * head_m
    return make_result(
        symbol="P_hyd",
        value=power,
        kind="power",
        formula="P_hyd = rho*g*Q*H",
        substitutions={
            "rho": format_value(density_kg_m3, "kg/m**3"),
            "g": format_value(_G, "m/s**2"),
            "Q": format_value(flow_m3s, "m**3/s"),
            "H": format_value(head_m, "m"),
        },
        citation=citation_for(hydraulic_power, editions),
        inputs_used=["density_kg_m3", "flow_m3_h", "head_m"],
    )


@provable(API_610, "power and driver sizing", "S7")
def absorbed_power(
    hydraulic_power_w: float,
    efficiency_fraction: float,
    editions: CodeEditions,
) -> Result:
    """Absorbed (shaft) power ``P_abs = P_hyd / eta`` (PU-6)."""
    require_positive(P_hyd=hydraulic_power_w)
    if not 0.0 < efficiency_fraction <= 1.0:
        raise ValueError(f"efficiency_fraction must lie in (0, 1], got {efficiency_fraction}")
    power = hydraulic_power_w / efficiency_fraction
    return make_result(
        symbol="P_abs",
        value=power,
        kind="power",
        formula="P_abs = P_hyd / eta",
        substitutions={
            "P_hyd": format_value(hydraulic_power_w, "W"),
            "eta": f"{efficiency_fraction:.4g}",
        },
        citation=citation_for(absorbed_power, editions),
        inputs_used=["efficiency_pct"],
    )


@provable(API_610, "power and driver sizing", "S7")
def motor_sizing(
    absorbed_power_w: float,
    editions: CodeEditions,
    margin_factor: float = 1.15,
) -> Result:
    """Size the driver with the API 610 / NEMA margin and a standard motor (PU-6)."""
    require_positive(P_abs=absorbed_power_w)
    if margin_factor < 1.0:
        raise ValueError(f"margin_factor must be >= 1, got {margin_factor}")
    required_w = absorbed_power_w * margin_factor
    selected_kw = next(
        (size for size in _STANDARD_MOTOR_KW if size * 1000.0 >= required_w),
        _STANDARD_MOTOR_KW[-1],
    )
    return make_result(
        symbol="P_motor",
        value=selected_kw * 1000.0,
        kind="power",
        formula="P_motor >= P_abs * margin; then round up to a standard motor",
        substitutions={
            "P_abs": format_value(absorbed_power_w, "W"),
            "margin": f"{margin_factor:.4g}",
            "required": format_value(required_w, "W"),
            "selected motor": f"{selected_kw:.6g} kW",
        },
        citation=citation_for(motor_sizing, editions),
        inputs_used=["efficiency_pct", "motor_margin"],
    )


@provable(API_610, "power and driver sizing", "S7")
def motor_current(
    absorbed_power_w: float,
    voltage_v: float,
    power_factor: float,
    phases: int,
    editions: CodeEditions,
) -> Result:
    """Rated motor current for the amp check (PU-6).

    ``I = P / (sqrt(3) * V * pf)`` for a three-phase motor and ``P/(V*pf)`` for a
    single-phase motor, with *P* the absorbed (shaft) power.
    """
    require_positive(P=absorbed_power_w, V=voltage_v, pf=power_factor)
    if phases not in (1, 3):
        raise ValueError(f"phases must be 1 or 3, got {phases}")
    denominator = voltage_v * power_factor
    if phases == 3:
        denominator *= math.sqrt(3.0)
    current = absorbed_power_w / denominator
    return make_result(
        symbol="I_motor",
        value=current,
        kind="dimensionless",
        unit="A",
        formula="I = P / (sqrt(3)*V*pf) three-phase; P/(V*pf) single-phase",
        substitutions={
            "P": format_value(absorbed_power_w, "W"),
            "V": f"{voltage_v:.6g} V",
            "pf": f"{power_factor:.4g}",
            "phases": str(phases),
        },
        citation=citation_for(motor_current, editions),
        inputs_used=["motor_voltage_v", "motor_power_factor", "motor_phases"],
    )


# ---------------------------------------------------------------------------
# PU-7 — casing pressure design
# ---------------------------------------------------------------------------


@provable(ASME_VIII_1, "UG-27(c)(1)", "S1")
def casing_wall_thickness(
    pressure_pa: float,
    inside_radius_m: float,
    allowable_stress_pa: float,
    joint_efficiency: float,
    editions: CodeEditions,
    corrosion_allowance_m: float = 0.0,
) -> Result:
    """Casing wall pressure thickness by the ASME VIII-1 UG-27(c)(1) method (PU-7)."""
    return shell_calc.circumferential_thickness(
        pressure_pa,
        inside_radius_m,
        allowable_stress_pa,
        joint_efficiency,
        editions,
        corrosion_allowance_m,
    )


@provable(ASME_VIII_1, "UG-27(c)(1)", "S1")
def casing_mawp(
    pressure_thickness_m: float,
    inside_radius_m: float,
    allowable_stress_pa: float,
    joint_efficiency: float,
    editions: CodeEditions,
) -> Result:
    """Casing MAWP from the as-built metal thickness (PU-7, UG-27 inversion)."""
    return shell_calc.circumferential_mawp(
        pressure_thickness_m,
        inside_radius_m,
        allowable_stress_pa,
        joint_efficiency,
        editions,
    )


@provable(API_610, "casing hydrostatic test", "S7")
def casing_hydrotest_pressure(
    mawp_pa: float,
    editions: CodeEditions,
    factor: float = CASING_TEST_FACTOR,
) -> Result:
    """Casing hydrostatic test pressure ``P_T = factor * MAWP`` (PU-7, API 610)."""
    require_positive(MAWP=mawp_pa, factor=factor)
    test = factor * mawp_pa
    return make_result(
        symbol="P_T",
        value=test,
        kind="pressure",
        formula="P_T = factor * MAWP",
        substitutions={
            "MAWP": format_value(mawp_pa, "Pa"),
            "factor": f"{factor:.4g}",
        },
        citation=citation_for(casing_hydrotest_pressure, editions),
        inputs_used=["design_pressure_mpa", "provided_casing_thickness_mm"],
    )


# ---------------------------------------------------------------------------
# PU-8 — shaft
# ---------------------------------------------------------------------------


@provable(API_610, "shaft torque and combined stress", "S7")
def shaft_torque(power_w: float, angular_speed_rad_s: float, editions: CodeEditions) -> Result:
    """Transmitted torque ``T = P / omega`` (PU-8)."""
    require_positive(P=power_w, omega=angular_speed_rad_s)
    torque = power_w / angular_speed_rad_s
    return make_result(
        symbol="T_shaft",
        value=torque,
        kind="torque",
        formula="T = P / omega",
        substitutions={
            "P": format_value(power_w, "W"),
            "omega": format_value(angular_speed_rad_s, "rad/s"),
        },
        citation=citation_for(shaft_torque, editions),
        inputs_used=["efficiency_pct", "rated_speed_rpm"],
    )


@provable(API_610, "shaft torque and combined stress", "S7")
def shaft_bending_moment(
    radial_load_n: float,
    distance_a_m: float,
    distance_b_m: float,
    editions: CodeEditions,
) -> Result:
    """Bending moment from a load between two supports, ``M = F*a*b/(a+b)`` (PU-8)."""
    require_positive(F=radial_load_n, a=distance_a_m, b=distance_b_m)
    span = distance_a_m + distance_b_m
    moment = radial_load_n * distance_a_m * distance_b_m / span
    return make_result(
        symbol="M_shaft",
        value=moment,
        kind="torque",
        formula="M = F*a*b/(a+b)",
        substitutions={
            "F": format_value(radial_load_n, "N"),
            "a": format_value(distance_a_m, "m"),
            "b": format_value(distance_b_m, "m"),
        },
        citation=citation_for(shaft_bending_moment, editions),
        inputs_used=["shaft_radial_load_n", "shaft_load_offset_mm", "shaft_bearing_span_mm"],
    )


@provable(API_610, "shaft deflection at seal chamber", "S7")
def seal_chamber_deflection(
    radial_load_n: float,
    distance_a_m: float,
    distance_b_m: float,
    modulus_pa: float,
    second_moment_m4: float,
    editions: CodeEditions,
    limit_m: float = SEAL_DEFLECTION_LIMIT_M,
) -> Result:
    """Shaft deflection at the load, ``delta = F*a^2*b^2/(3*E*I*(a+b))`` (PU-8).

    The result is checked against the API 610 seal-chamber limit (0.05 mm).
    """
    require_positive(F=radial_load_n, a=distance_a_m, b=distance_b_m, E=modulus_pa, I=second_moment_m4)
    if limit_m <= 0:
        raise ValueError(f"limit_m must be > 0, got {limit_m}")
    span = distance_a_m + distance_b_m
    deflection = (
        radial_load_n * distance_a_m**2 * distance_b_m**2 / (3.0 * modulus_pa * second_moment_m4 * span)
    )
    verdict, margin = margin_verdict(limit_m, deflection)
    return make_result(
        symbol="delta_seal",
        value=deflection,
        kind="length",
        formula="delta = F*a^2*b^2/(3*E*I*(a+b)) <= API 610 limit",
        substitutions={
            "F": format_value(radial_load_n, "N"),
            "a": format_value(distance_a_m, "m"),
            "b": format_value(distance_b_m, "m"),
            "E": format_value(modulus_pa, "Pa"),
            "I": format_value(second_moment_m4, "m**4"),
            "limit": format_value(limit_m, "m"),
        },
        citation=citation_for(seal_chamber_deflection, editions),
        inputs_used=["shaft_radial_load_n", "shaft_diameter_mm", "shaft_bearing_span_mm"],
        verdict=verdict,
        margin=margin,
    )


@provable(API_610, "shaft torque and combined stress", "S7")
def combined_shaft_stress(
    bending_moment_nm: float,
    torque_nm: float,
    diameter_m: float,
    editions: CodeEditions,
) -> Result:
    """von Mises equivalent stress from combined bending and torsion (PU-8).

    ``sigma_b = 32*M/(pi*d^3)``, ``tau = 16*T/(pi*d^3)`` and
    ``sigma_eq = sqrt(sigma_b^2 + 3*tau^2)``.
    """
    require_positive(M=bending_moment_nm, T=torque_nm, d=diameter_m)
    section = math.pi * diameter_m**3
    bending_stress = 32.0 * bending_moment_nm / section
    shear_stress = 16.0 * torque_nm / section
    equivalent = math.sqrt(bending_stress**2 + 3.0 * shear_stress**2)
    return make_result(
        symbol="sigma_eq",
        value=equivalent,
        kind="stress",
        formula="sigma_eq = sqrt(sigma_b^2 + 3*tau^2); sigma_b=32M/(pi d^3), tau=16T/(pi d^3)",
        substitutions={
            "M": format_value(bending_moment_nm, "N*m"),
            "T": format_value(torque_nm, "N*m"),
            "d": format_value(diameter_m, "m"),
            "sigma_b": format_value(bending_stress, "Pa"),
            "tau": format_value(shear_stress, "Pa"),
        },
        citation=citation_for(combined_shaft_stress, editions),
        inputs_used=["shaft_diameter_mm", "shaft_radial_load_n"],
    )


@provable(API_610, "shaft torque and combined stress", "S7")
def shaft_safety_factor(
    yield_strength_pa: float,
    equivalent_stress_pa: float,
    editions: CodeEditions,
) -> Result:
    """Shaft safety factor on yield ``SF = Sy / sigma_eq`` (PU-8)."""
    require_positive(Sy=yield_strength_pa, sigma_eq=equivalent_stress_pa)
    factor = yield_strength_pa / equivalent_stress_pa
    return make_result(
        symbol="SF_shaft",
        value=factor,
        kind="dimensionless",
        formula="SF = Sy / sigma_eq",
        substitutions={
            "Sy": format_value(yield_strength_pa, "Pa"),
            "sigma_eq": format_value(equivalent_stress_pa, "Pa"),
        },
        citation=citation_for(shaft_safety_factor, editions),
        inputs_used=["shaft_diameter_mm"],
        verdict=Verdict.PASS if factor >= 1.0 else Verdict.FAIL,
        margin=factor - 1.0,
    )


# ---------------------------------------------------------------------------
# PU-9 — bearing life
# ---------------------------------------------------------------------------


@provable(ISO_281, "rating life L10", "S19")
def bearing_life(
    dynamic_load_n: float,
    equivalent_load_n: float,
    speed_rpm: float,
    editions: CodeEditions,
    exponent: float = 3.0,
    minimum_life_h: float = MIN_BEARING_LIFE_H,
) -> Result:
    """Bearing rating life ``L10h = (1e6/(60*n))*(C/P)^p`` (PU-9, ISO 281).

    Reported in hours and checked against the API 610 minimum required life at
    rated continuous conditions.
    """
    require_positive(C=dynamic_load_n, P=equivalent_load_n, n=speed_rpm)
    if exponent <= 0:
        raise ValueError(f"exponent must be > 0, got {exponent}")
    if minimum_life_h <= 0:
        raise ValueError(f"minimum_life_h must be > 0, got {minimum_life_h}")
    life_h = (1.0e6 / (60.0 * speed_rpm)) * (dynamic_load_n / equivalent_load_n) ** exponent
    verdict, margin = margin_verdict(life_h, minimum_life_h)
    return make_result(
        symbol="L10h",
        value=life_h,
        kind="dimensionless",
        unit="h",
        formula="L10h = (10^6/(60*n)) * (C/P)^p",
        substitutions={
            "C": format_value(dynamic_load_n, "N"),
            "P": format_value(equivalent_load_n, "N"),
            "n": f"{speed_rpm:.6g} rpm",
            "p": f"{exponent:.4g}",
            "minimum": f"{minimum_life_h:.6g} h",
        },
        citation=citation_for(bearing_life, editions),
        inputs_used=[
            "radial_bearing_dynamic_load_n",
            "radial_bearing_load_n",
            "rated_speed_rpm",
            "bearing_type",
            "min_bearing_life_h",
        ],
        verdict=verdict,
        margin=margin,
    )


# ---------------------------------------------------------------------------
# PU-10 — mechanical seal selection
# ---------------------------------------------------------------------------


@provable(API_682, "seal category / arrangement / flush plan", "S8",
          verification=VerificationStatus.EXPERIMENTAL)
def seal_selection(
    temperature_c: float,
    seal_chamber_pressure_pa: float,
    service: str,
    hazardous: bool,
    solids: bool,
    editions: CodeEditions,
) -> Result:
    """Screening mechanical-seal selection per API 682 (PU-10).

    EXPERIMENTAL and screening only: category, arrangement, face materials and
    flush plan follow the published API 682 decision rules in simplified form and
    must be confirmed by the seal vendor for the actual fluid and duty.
    """
    if seal_chamber_pressure_pa < 0:
        raise ValueError(f"seal_chamber_pressure_pa must be >= 0, got {seal_chamber_pressure_pa}")
    pressure_mpa = seal_chamber_pressure_pa / 1.0e6
    if temperature_c > 204.0 or pressure_mpa > 2.76:
        category = 3
    elif temperature_c > 150.0 or pressure_mpa > 1.0 or hazardous:
        category = 2
    else:
        category = 1

    if category == 3 or hazardous:
        arrangement = 3
        containment = "dual pressurised (Arrangement 3) with pressurised barrier fluid"
    elif category == 2:
        arrangement = 2
        containment = "dual unpressurised (Arrangement 2) with unpressurised barrier fluid"
    else:
        arrangement = 1
        containment = "single seal (Arrangement 1)"

    if arrangement == 3:
        plan = "53 or 54 (pressurised barrier)"
    elif arrangement == 2:
        plan = "52 (unpressurised barrier)"
    elif solids:
        plan = "32 (clean flush)"
    elif temperature_c > 150.0:
        plan = "21 or 23 (hot service quench)"
    else:
        plan = "11 (self flush from discharge)"

    if solids or temperature_c > 150.0:
        faces = "silicon carbide / silicon carbide"
    elif "water" in service.lower():
        faces = "carbon / silicon carbide"
    else:
        faces = "carbon / silicon carbide (general hydrocarbon service)"

    citation = citation_for(seal_selection, editions)
    return make_result(
        symbol="seal_arrangement",
        value=float(category),
        kind="dimensionless",
        formula="API 682 decision rules: category, arrangement, faces and flush plan",
        substitutions={
            "category": f"Category {category}",
            "arrangement": f"Arrangement {arrangement}",
            "containment": containment,
            "faces": faces,
            "flush plan": f"Plan {plan}",
            "pressure": format_value(seal_chamber_pressure_pa, "Pa"),
            "temperature": format_value(temperature_c, "degC"),
            "service": service,
        },
        citation=citation,
        inputs_used=["temperature_c", "seal_chamber_pressure_mpa", "seal_hazardous", "seal_solids"],
        verification=VerificationStatus.EXPERIMENTAL,
        issues=[
            _warning(
                citation,
                "Mechanical seal selection is screening only: verify the arrangement "
                "and flush plan with the seal vendor.",
                "API 682 selection depends on fluid properties, containment philosophy "
                "and plant practice not captured by this rule set.",
            )
        ],
    )


# ---------------------------------------------------------------------------
# PU-11 — nozzle loads
# ---------------------------------------------------------------------------


@provable(API_610, "nozzle loads", "S7", verification=VerificationStatus.EXPERIMENTAL)
def nozzle_load_check(
    force_n: float,
    moment_nm: float,
    allowable_force_n: float,
    allowable_moment_nm: float,
    editions: CodeEditions,
) -> Result:
    """Interaction check of a nozzle resultant force and moment (PU-11).

    ``ratio = sqrt((F/Fa)^2 + (M/Ma)^2) <= 1``. EXPERIMENTAL: the allowables are
    entered/simplified values; API 610 allowables depend on size, class and
    configuration.
    """
    require_positive(Fa=allowable_force_n, Ma=allowable_moment_nm)
    if force_n < 0 or moment_nm < 0:
        raise ValueError("force and moment resultants must be >= 0")
    ratio = math.sqrt((force_n / allowable_force_n) ** 2 + (moment_nm / allowable_moment_nm) ** 2)
    verdict = Verdict.PASS if ratio <= 1.0 else Verdict.FAIL
    citation = citation_for(nozzle_load_check, editions)
    return make_result(
        symbol="nozzle_load",
        value=ratio,
        kind="dimensionless",
        formula="ratio = sqrt((F/Fa)^2 + (M/Ma)^2) <= 1",
        substitutions={
            "F resultant": format_value(force_n, "N"),
            "M resultant": format_value(moment_nm, "N*m"),
            "Fa": format_value(allowable_force_n, "N"),
            "Ma": format_value(allowable_moment_nm, "N*m"),
        },
        citation=citation,
        inputs_used=["loads"],
        verdict=verdict,
        margin=1.0 - ratio,
        verification=VerificationStatus.EXPERIMENTAL,
        issues=[
            _warning(
                citation,
                "Nozzle-load allowables are screened from entered values; confirm "
                "against API 610 for the actual nozzle size and class.",
                "API 610 allowable nozzle loads depend on size, class and pump "
                "configuration and are not reproduced here.",
            )
        ],
    )


# ---------------------------------------------------------------------------
# PU-12 — material class
# ---------------------------------------------------------------------------


@provable(API_610, "material classes", "S7", verification=VerificationStatus.EXPERIMENTAL)
def material_class_selection(
    temperature_c: float,
    service: str,
    chloride_ppm: float,
    h2s_present: bool,
    editions: CodeEditions,
) -> Result:
    """Screening API 610 material-class selection with sour-service flags (PU-12).

    EXPERIMENTAL: the mapping is a simplified rule set and must be confirmed
    against API 610 material classes and, for sour service, NACE MR0175.
    """
    if chloride_ppm < 0:
        raise ValueError(f"chloride_ppm must be >= 0, got {chloride_ppm}")
    if h2s_present:
        material_class = "S-8 (austenitic) or D-1 (duplex) with NACE MR0175 compliance"
        note = "sour service: hardness and material limits per NACE MR0175 / ISO 15156"
    elif "water" in service.lower() and chloride_ppm > 50.0:
        material_class = "D-1 (duplex stainless)"
        note = "chloride-bearing water: review stress-corrosion cracking"
    elif temperature_c > 260.0:
        material_class = "A-8 (alloy steel / 12Cr) for elevated temperature"
        note = "elevated temperature: confirm mechanical properties at design temperature"
    elif "acid" in service.lower() or "corrosive" in service.lower():
        material_class = "S-6 (304 SS) or S-8 (316 SS)"
        note = "corrosive service: verify corrosion allowance and alloy suitability"
    else:
        material_class = "C-6 (carbon steel)"
        note = "non-corrosive service: carbon steel with a corrosion allowance"
    citation = citation_for(material_class_selection, editions)
    issues = [
        _warning(
            citation,
            "Material-class selection is a simplified screening rule set.",
            "Confirm against API 610 material classes and project corrosion studies.",
        )
    ]
    if h2s_present:
        issues.append(
            Issue(
                severity=Severity.WARNING,
                message=(
                    "Sour service indicated: apply NACE MR0175 / ISO 15156 hardness "
                    "and material limits."
                ),
                rationale="H2S-bearing streams require NACE-compliant materials.",
                citation=citation_of(NACE_MR0175, "sour service materials", editions, "S14"),
            )
        )
    return make_result(
        symbol="material_class",
        value=None,
        kind="dimensionless",
        unit="",
        formula="API 610 material class from service, temperature and chloride level",
        substitutions={
            "material class (screening)": material_class,
            "temperature": format_value(temperature_c, "degC"),
            "chloride": f"{chloride_ppm:.6g} ppm",
            "H2S": "present" if h2s_present else "not indicated",
            "note": note,
            "NACE": "NACE MR0175 / ISO 15156 flagged" if h2s_present else "not required",
        },
        citation=citation,
        inputs_used=["temperature_c", "service", "chloride_ppm", "h2s_present"],
        verification=VerificationStatus.EXPERIMENTAL,
        issues=issues,
    )


# ---------------------------------------------------------------------------
# PU-13 — vibration
# ---------------------------------------------------------------------------


@provable(API_610, "vibration limits", "S7")
def vibration_check(
    velocity_m_s: float,
    editions: CodeEditions,
    limit_m_s: float = VIBRATION_LIMIT_M_S,
) -> Result:
    """Check overall vibration velocity against the API 610 limit (PU-13)."""
    if velocity_m_s < 0:
        raise ValueError(f"velocity_m_s must be >= 0, got {velocity_m_s}")
    require_positive(limit=limit_m_s)
    verdict, margin = margin_verdict(limit_m_s, velocity_m_s) if velocity_m_s > 0 else (Verdict.PASS, 1.0)
    return make_result(
        symbol="v_rms",
        value=velocity_m_s,
        kind="velocity",
        formula="v_rms <= API 610 limit",
        substitutions={
            "v_rms": format_value(velocity_m_s, "m/s"),
            "limit": format_value(limit_m_s, "m/s"),
        },
        citation=citation_for(vibration_check, editions),
        inputs_used=["vibration_velocity_mm_s"],
        verdict=verdict,
        margin=margin,
    )
