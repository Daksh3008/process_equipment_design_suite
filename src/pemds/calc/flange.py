"""Flange rating, bolting and mating-pair calculations — ASME B16.5 / B16.20.

STATUS: EXPERIMENTAL. The pressure-temperature ratings, bolting dimensions and
gasket m/y factors are read from small, provenance-stamped *demonstration* data
files whose ``checked_by`` reads ``UNVERIFIED``. The data policy therefore
requires every result below to be surfaced as ``EXPERIMENTAL`` and to carry a
warning: these numbers are placeholders pending transcription from the licensed
editions and must not back a verified design.

The lookups always read the tabulated value at the *next-higher* temperature
step (never an interpolation), so the reported rating is conservative.

Only short paraphrases and minimal numeric values are stored; no standard table
or prose is reproduced.
"""

from __future__ import annotations

import math
from bisect import bisect_left
from itertools import pairwise

from ..core.calc import CodeEditions, citation_for, citation_of, provable
from ..core.provenance import Provenance, VerificationStatus
from ..core.result import Issue, Result, Severity, Verdict
from ..core.standards import ASME_B16_5, ASME_B16_20
from ..core.units import format_value
from ..data.loader import load_package_data
from .common import make_result, margin_verdict, require_positive

_MM_PER_M = 1000.0
_MPA_PER_PA = 1.0e-6
_PA_PER_MPA = 1.0e6

_CLAUSE_RATINGS = "Section 2, pressure-temperature ratings"
_CLAUSE_BOLTING = "Bolting dimensions and materials"
_CLAUSE_MATING = "Flange facing and mating dimensions"
_CLAUSE_GASKET = "Gasket m and y factors"

_MPA = 1.0e6


def _require_ascending(points: tuple[tuple[float, float], ...], label: str) -> None:
    temps = [p[0] for p in points]
    if any(not math.isfinite(t) for t in temps):
        raise ValueError(f"{label} contains a non-finite temperature: {temps}")
    if any(b <= a for a, b in pairwise(temps)):
        raise ValueError(f"{label} temperatures must be strictly ascending, got {temps}")


def _load_ratings() -> tuple[
    dict[tuple[str, int], tuple[frozenset[str], tuple[tuple[float, float], ...]]],
    frozenset[str],
    tuple[str, ...],
    tuple[int, ...],
    Provenance,
]:
    data_file = load_package_data("tables/b165_ratings.json")
    index: dict[tuple[str, int], tuple[frozenset[str], tuple[tuple[float, float], ...]]] = {}
    sizes: set[str] = set()
    groups: set[str] = set()
    classes: set[int] = set()
    for row in data_file.data["ratings"]:
        group = str(row["material_group"])
        pressure_class = int(row["pressure_class"])
        row_sizes = frozenset(str(s) for s in row["sizes"])
        points = tuple((float(t), float(p) * _MPA) for t, p in row["points_MPa"])
        _require_ascending(points, f"ratings[{group}/{pressure_class}]")
        key = (group, pressure_class)
        if key in index:
            raise ValueError(f"duplicate rating row for group {group!r} class {pressure_class}")
        index[key] = (row_sizes, points)
        sizes |= row_sizes
        groups.add(group)
        classes.add(pressure_class)
    if not index:
        raise ValueError("b165_ratings.json contains no rating rows")
    return index, frozenset(sizes), tuple(sorted(groups)), tuple(sorted(classes)), data_file.provenance


def _load_bolting() -> tuple[
    dict[tuple[str, int], tuple[int, float, float, str]], Provenance
]:
    data_file = load_package_data("tables/b165_bolting.json")
    index: dict[tuple[str, int], tuple[int, float, float, str]] = {}
    for row in data_file.data["bolting"]:
        key = (str(row["nps"]), int(row["pressure_class"]))
        if key in index:
            raise ValueError(f"duplicate bolting row for NPS {key[0]!r} class {key[1]}")
        index[key] = (
            int(row["bolt_count"]),
            float(row["bolt_diameter_mm"]) / _MM_PER_M,
            float(row["bolt_tensile_area_mm2"]) * 1.0e-6,
            str(row["bolt_material"]),
        )
    if not index:
        raise ValueError("b165_bolting.json contains no bolting rows")
    return index, data_file.provenance


def _load_gaskets() -> tuple[dict[str, tuple[float, float, float, float, str]], Provenance]:
    data_file = load_package_data("tables/b16_20_gaskets.json")
    index: dict[str, tuple[float, float, float, float, str]] = {}
    for row in data_file.data["gaskets"]:
        key = str(row["gasket_type"])
        if key in index:
            raise ValueError(f"duplicate gasket row for type {key!r}")
        index[key] = (
            float(row["m"]),
            float(row["y_MPa"]) * _MPA,
            float(row["thickness_mm"]) / _MM_PER_M,
            float(row["contact_width_mm"]) / _MM_PER_M,
            str(row["description"]),
        )
    if not index:
        raise ValueError("b16_20_gaskets.json contains no gasket rows")
    return index, data_file.provenance


_RATINGS, _RATING_SIZES, _MATERIAL_GROUPS, _PRESSURE_CLASSES, _RATINGS_PROVENANCE = _load_ratings()
_BOLTING, _BOLTING_PROVENANCE = _load_bolting()
_GASKETS, _GASKET_PROVENANCE = _load_gaskets()

def _provisional(provenance: Provenance) -> bool:
    return "UNVERIFIED" in provenance.checked_by.upper()


def _rating_status(citation) -> tuple[VerificationStatus, Issue | None]:
    if _provisional(_RATINGS_PROVENANCE):
        return VerificationStatus.EXPERIMENTAL, Issue(
            severity=Severity.WARNING,
            message=(
                "B16.5 pressure-temperature rating data is provisional "
                f"({_RATINGS_PROVENANCE.checked_by})."
            ),
            rationale="Data policy: unreviewed rating data must not back a verified result.",
            citation=citation,
        )
    return VerificationStatus.VERIFIED, None


def _step_rating(points: tuple[tuple[float, float], ...], temperature_c: float) -> float:
    """Rating at *temperature_c* from the next-higher tabulated step (conservative)."""
    if not math.isfinite(temperature_c):
        raise ValueError(f"temperature must be finite, got {temperature_c}")
    temps = [p[0] for p in points]
    if temperature_c < temps[0] or temperature_c > temps[-1]:
        raise ValueError(
            f"temperature {temperature_c:g} degC is outside the tabulated rating range "
            f"({temps[0]:g} to {temps[-1]:g} degC)"
        )
    index = bisect_left(temps, temperature_c)
    return points[index][1]


def known_sizes() -> tuple[str, ...]:
    """The NPS sizes present in the rating table (for input validation)."""
    return tuple(sorted(_RATING_SIZES))


def known_material_groups() -> tuple[str, ...]:
    """The B16.5 material group identifiers present in the rating table."""
    return _MATERIAL_GROUPS


def known_pressure_classes() -> tuple[int, ...]:
    """The pressure classes present in the rating table, ascending."""
    return _PRESSURE_CLASSES


def known_gasket_types() -> tuple[str, ...]:
    """The gasket types present in the gasket table."""
    return tuple(sorted(_GASKETS))


def rating_temperature_range() -> tuple[float, float]:
    """The overall tabulated rating temperature range in degC."""
    lows: list[float] = []
    highs: list[float] = []
    for _sizes, points in _RATINGS.values():
        lows.append(points[0][0])
        highs.append(points[-1][0])
    return min(lows), max(highs)


def gasket_factors(gasket_type: str) -> tuple[float, float]:
    """Return ``(m, y_Pa)`` for a gasket type."""
    try:
        m, y_pa, _thickness, _width, _description = _GASKETS[gasket_type]
    except KeyError as exc:
        raise ValueError(
            f"unknown gasket type {gasket_type!r}; available: {sorted(_GASKETS)}"
        ) from exc
    return m, y_pa


def gasket_contact_width_m(gasket_type: str) -> float:
    """The tabulated gasket contact width in metres."""
    try:
        return _GASKETS[gasket_type][3]
    except KeyError as exc:
        raise ValueError(
            f"unknown gasket type {gasket_type!r}; available: {sorted(_GASKETS)}"
        ) from exc


def effective_gasket_width_m(contact_width_m: float) -> float:
    """Effective gasket seating width ``b`` from the contact width ``N`` (App. 2 form).

    ``b0 = N / 2``; for ``b0`` wider than 6.35 mm the seating width is reduced by
    the ``2.52*sqrt(b0)`` relation, else ``b = b0``.
    """
    require_positive(contact_width_m=contact_width_m)
    b0_mm = contact_width_m * _MM_PER_M / 2.0
    b_mm = b0_mm if b0_mm <= 6.35 else 2.52 * math.sqrt(b0_mm)
    return b_mm / _MM_PER_M


def bolt_spec(size: str, pressure_class: int) -> tuple[int, float, float, str]:
    """Return ``(count, diameter_m, tensile_area_m2, material)`` for a size/class."""
    try:
        return _BOLTING[(str(size), int(pressure_class))]
    except KeyError as exc:
        raise ValueError(
            f"no bolting data for NPS {size!r} class {pressure_class}; "
            f"available sizes: {sorted({key[0] for key in _BOLTING})}"
        ) from exc


@provable(ASME_B16_5, _CLAUSE_RATINGS, "S3")
def pressure_temp_rating(
    size: str,
    material_group: str,
    pressure_class: int,
    temperature_c: float,
    editions: CodeEditions,
) -> Result:
    """Allowable pressure of a Class/size/material group at a design temperature.

    Reads the tabulated rating at the next-higher temperature step. The backing
    table is a provisional demonstration set, so the result is EXPERIMENTAL and
    carries the data warning (VAL-2).
    """
    size_key = str(size)
    key = (str(material_group), int(pressure_class))
    try:
        row_sizes, points = _RATINGS[key]
    except KeyError as exc:
        raise ValueError(
            f"no rating data for material group {material_group!r} class {pressure_class}; "
            f"available: {sorted(_RATINGS)}"
        ) from exc
    if size_key not in row_sizes:
        raise ValueError(
            f"NPS {size_key!r} is not tabulated for group {material_group!r} "
            f"class {pressure_class}; available sizes: {sorted(row_sizes)}"
        )
    rating = _step_rating(points, temperature_c)
    citation = citation_for(pressure_temp_rating, editions)
    status, issue = _rating_status(citation)
    return make_result(
        symbol="P_rating",
        value=rating,
        kind="pressure",
        formula="P_rating = tabulated B16.5 rating at the next-higher temperature step",
        substitutions={
            "size (NPS)": size_key,
            "material group": str(material_group),
            "class": str(int(pressure_class)),
            "temperature": f"{temperature_c:g} degC",
            "tabulated steps (MPa)": ", ".join(
                f"{t:g}:{p * _MPA_PER_PA:g}" for t, p in points
            ),
        },
        citation=citation,
        inputs_used=["size", "material_group", "pressure_class", "temperature_c"],
        verification=status,
        issues=[issue] if issue is not None else [],
    )


def _rating_value(
    size: str, material_group: str, pressure_class: int, temperature_c: float, editions: CodeEditions
) -> Result:
    return pressure_temp_rating(size, material_group, pressure_class, temperature_c, editions)


@provable(ASME_B16_5, _CLAUSE_RATINGS, "S3")
def select_class(
    size: str,
    material_group: str,
    design_pressure_pa: float,
    temperature_c: float,
    editions: CodeEditions,
    minimum_class: int | None = None,
) -> Result:
    """Select the lowest pressure class whose rating at temperature meets the design.

    ``minimum_class`` optionally raises the floor (a user preference). When no
    tabulated class qualifies the highest available class is reported with a
    FAIL verdict and a nearest-upgrade note.
    """
    require_positive(design_pressure_pa=design_pressure_pa)
    floor = int(minimum_class) if minimum_class is not None else None
    if floor is not None and floor not in _PRESSURE_CLASSES:
        raise ValueError(
            f"requested class {floor} is not tabulated; available: {list(_PRESSURE_CLASSES)}"
        )
    candidates = [c for c in _PRESSURE_CLASSES if floor is None or c >= floor]
    if not candidates:
        raise ValueError(
            f"no tabulated class at or above requested class {floor}; "
            f"available: {list(_PRESSURE_CLASSES)}"
        )

    children: list[Result] = []
    selected: int | None = None
    for candidate in candidates:
        rating = _rating_value(size, material_group, candidate, temperature_c, editions)
        children.append(rating)
        if selected is None and rating.value is not None and rating.value >= design_pressure_pa:
            selected = candidate

    issues: list[Issue] = []
    status, issue = _rating_status(citation_for(select_class, editions))
    if issue is not None:
        issues.append(issue)

    if selected is None:
        selected = candidates[-1]
        selected_rating = _find_rating(children, selected)
        if selected_rating.value is None:
            raise ValueError(
                f"no rating value for Class {selected} at size {size!r}, group {material_group!r}"
            )
        verdict = Verdict.FAIL
        margin = (selected_rating.value - design_pressure_pa) / design_pressure_pa
        issues.append(
            Issue(
                severity=Severity.WARNING,
                message=(
                    f"design pressure {format_value(design_pressure_pa, 'Pa')} exceeds the "
                    f"Class {selected} rating at {temperature_c:g} degC; the nearest upgrade "
                    "is a higher class or a B16.47 series flange, then re-check."
                ),
                rationale=(
                    "No tabulated B16.5 class up to the maximum in this data set qualifies; "
                    "the selection is reported as a failure with the nearest upgrade."
                ),
                citation=citation_for(select_class, editions),
            )
        )
    else:
        selected_rating = _find_rating(children, selected)
        if selected_rating.value is None:
            raise ValueError(
                f"no rating value for Class {selected} at size {size!r}, group {material_group!r}"
            )
        verdict, margin = margin_verdict(selected_rating.value, design_pressure_pa)
    if selected_rating.value is None:  # pragma: no cover - guarded in both branches above
        raise ValueError(f"no rating value for Class {selected} at size {size!r}")
    selected_rating_value = selected_rating.value

    return make_result(
        symbol="class",
        value=float(selected),
        kind="dimensionless",
        formula="class = lowest pressure class with P_rating(T) >= P_design",
        substitutions={
            "size (NPS)": str(size),
            "material group": str(material_group),
            "design pressure": format_value(design_pressure_pa, "Pa"),
            "temperature": f"{temperature_c:g} degC",
            "selected class": str(selected),
            "rating at selected class": format_value(selected_rating_value, "Pa"),
        },
        citation=citation_for(select_class, editions),
        inputs_used=["size", "material_group", "design_pressure_pa", "temperature_c"],
        verdict=verdict,
        margin=margin,
        verification=status,
        children=children,
        issues=issues,
    )


def _find_rating(children: list[Result], pressure_class: int) -> Result:
    wanted = str(int(pressure_class))
    for child in children:
        if child.substitutions.get("class") == wanted:
            return child
    raise ValueError(f"internal error: rating for class {pressure_class} was not computed")


@provable(ASME_B16_5, _CLAUSE_BOLTING, "S3", verification=VerificationStatus.EXPERIMENTAL)
def bolt_up_check(
    design_pressure_pa: float,
    gasket_mean_diameter_m: float,
    gasket_effective_width_m: float,
    gasket_m: float,
    gasket_y_pa: float,
    bolt_count: int,
    bolt_tensile_area_m2: float,
    bolt_diameter_m: float,
    allowable_bolt_stress_pa: float,
    nut_factor: float,
    editions: CodeEditions,
) -> Result:
    """Bolt-area and target-torque check for a bolted flange joint. EXPERIMENTAL.

    Uses the gasket seating and operating loads of the B16.5/VIII-1 App. 2 form:
    ``H = pi/4 G^2 P``, ``Hp = 2 b pi G m P``, ``Wm1 = H + Hp``,
    ``Wm2 = pi b G y``, and ``Am = max(Wm1/Sb, Wm2/Sa)``. The target torque is
    ``T = K D (W/n)`` with a documented nut factor ``K``. This is a subset of the
    full flange design method and carries the experimental disclosure.
    """
    require_positive(
        P=design_pressure_pa,
        G=gasket_mean_diameter_m,
        b=gasket_effective_width_m,
        m=gasket_m,
        y=gasket_y_pa,
        A_bolt=bolt_tensile_area_m2,
        D_bolt=bolt_diameter_m,
        S_bolt=allowable_bolt_stress_pa,
        K=nut_factor,
    )
    if bolt_count <= 0:
        raise ValueError(f"bolt_count must be > 0, got {bolt_count}")

    hydrostatic = math.pi / 4.0 * gasket_mean_diameter_m**2 * design_pressure_pa
    gasket_operating = (
        2.0
        * gasket_effective_width_m
        * math.pi
        * gasket_mean_diameter_m
        * gasket_m
        * design_pressure_pa
    )
    operating_load = hydrostatic + gasket_operating
    seating_load = (
        math.pi * gasket_effective_width_m * gasket_mean_diameter_m * gasket_y_pa
    )
    am_operating = operating_load / allowable_bolt_stress_pa
    am_seating = seating_load / allowable_bolt_stress_pa
    required_area = max(am_operating, am_seating)
    available_area = bolt_count * bolt_tensile_area_m2
    governing = "seating" if seating_load >= operating_load else "operating"
    target_load = max(operating_load, seating_load)
    target_torque = nut_factor * bolt_diameter_m * (target_load / bolt_count)
    verdict, margin = margin_verdict(available_area, required_area)

    citation = citation_for(bolt_up_check, editions)
    gasket_citation = citation_of(ASME_B16_20, _CLAUSE_GASKET, editions)
    issues = [
        Issue(
            severity=Severity.WARNING,
            message=(
                "Bolt-up uses a simplified App. 2 load form and a user nut factor; "
                "verify the full flange and the torque-preload procedure."
            ),
            rationale=(
                "The coefficient-carrying flange stress checks and the torque-preload "
                "spreadsheet (lubrication, scatter) are not reproduced."
            ),
            citation=citation,
        )
    ]
    if _provisional(_GASKET_PROVENANCE):
        issues.append(
            Issue(
                severity=Severity.WARNING,
                message=(
                    "Gasket m/y data is provisional "
                    f"({_GASKET_PROVENANCE.checked_by})."
                ),
                rationale=(
                    "Data policy: unreviewed gasket data must not back a verified result."
                ),
                citation=gasket_citation,
            )
        )

    gasket_m_child = make_result(
        symbol="m",
        value=gasket_m,
        kind="dimensionless",
        formula="m = gasket factor (seating vs operating)",
        substitutions={
            "gasket type": "from data table",
            "m": f"{gasket_m:g}",
        },
        citation=gasket_citation,
        inputs_used=["gasket_m"],
        verification=VerificationStatus.EXPERIMENTAL,
    )
    if _provisional(_GASKET_PROVENANCE):
        gasket_m_child.issues.append(issues[-1])

    return make_result(
        symbol="bolt_up",
        value=available_area,
        kind="area",
        formula="Ab >= Am = max(Wm1/Sa, Wm2/Sb);  T = K*D*(W/n)",
        substitutions={
            "P": format_value(design_pressure_pa, "Pa"),
            "G (gasket mean dia)": format_value(gasket_mean_diameter_m, "m"),
            "b (effective width)": format_value(gasket_effective_width_m, "m"),
            "H (hydrostatic end)": format_value(hydrostatic, "N"),
            "Hp (gasket operating)": format_value(gasket_operating, "N"),
            "Wm1 (operating)": format_value(operating_load, "N"),
            "Wm2 (seating)": format_value(seating_load, "N"),
            "governing load": governing,
            "Am (required)": format_value(required_area, "m**2"),
            "Ab (available)": format_value(available_area, "m**2"),
            "target torque": format_value(target_torque, "N*m"),
        },
        citation=citation,
        inputs_used=[
            "design_pressure_mpa",
            "gasket_type",
            "bolt_count",
            "bolt_tensile_area_m2",
            "bolt_diameter_m",
            "nut_factor_k",
            "bolt_allowable_stress_mpa",
        ],
        verdict=verdict,
        margin=margin,
        verification=VerificationStatus.EXPERIMENTAL,
        children=[
            _force_result("H", hydrostatic, citation),
            _force_result("Hp", gasket_operating, citation),
            _force_result("Wm1", operating_load, citation),
            _force_result("Wm2", seating_load, citation),
            make_result(
                symbol="Am",
                value=required_area,
                kind="area",
                formula="Am = max(Wm1/Sa, Wm2/Sb)",
                substitutions={
                    "Wm1/Sa": format_value(am_operating, "m**2"),
                    "Wm2/Sb": format_value(am_seating, "m**2"),
                },
                citation=citation,
                inputs_used=["bolt_tensile_area_m2"],
            ),
            make_result(
                symbol="T_bolt",
                value=target_torque,
                kind="torque",
                formula="T = K*D*(W/n)",
                substitutions={
                    "K (nut factor)": f"{nut_factor:g}",
                    "D (bolt dia)": format_value(bolt_diameter_m, "m"),
                    "W (target load)": format_value(target_load, "N"),
                    "n (bolt count)": str(bolt_count),
                },
                citation=citation,
                inputs_used=["nut_factor_k", "bolt_diameter_m"],
            ),
            gasket_m_child,
        ],
        issues=issues,
    )


def _force_result(symbol: str, value: float, citation) -> Result:
    return make_result(
        symbol=symbol,
        value=value,
        kind="force",
        formula=f"{symbol} from the App. 2 bolted-flange load form",
        substitutions={symbol: format_value(value, "N")},
        citation=citation,
    )


@provable(ASME_B16_5, _CLAUSE_MATING, "S3", verification=VerificationStatus.EXPERIMENTAL)
def mating_flange_pair(
    size: str,
    pressure_class: int,
    facing: str,
    gasket_type: str,
    bolt_count: int,
    bolt_diameter_mm: float,
    editions: CodeEditions,
) -> Result:
    """Describe the mating flange pair for a connection. EXPERIMENTAL.

    Reports the size/class/facing pair with the selected gasket and bolt set.
    This is an identity pairing for the schedule, not a full dimensional
    interference check.
    """
    if bolt_count <= 0:
        raise ValueError(f"bolt_count must be > 0, got {bolt_count}")
    require_positive(bolt_diameter_mm=bolt_diameter_mm)
    if gasket_type not in _GASKETS:
        raise ValueError(
            f"unknown gasket type {gasket_type!r}; available: {sorted(_GASKETS)}"
        )
    citation = citation_for(mating_flange_pair, editions)
    issues = [
        Issue(
            severity=Severity.WARNING,
            message=(
                "The mating pair is an identity pairing from the schedule; full B16.5 "
                "dimensional and facing compatibility is not checked."
            ),
            rationale="Only the pair identity, gasket type and bolt set are reported.",
            citation=citation,
        )
    ]
    def _pair(symbol: str, value: float) -> Result:
        return make_result(
            symbol=symbol,
            value=value,
            kind="dimensionless",
            formula="flange = one B16.5 flange in the mating pair",
            substitutions={
                "size (NPS)": str(size),
                "class": str(int(pressure_class)),
                "facing": facing,
            },
            citation=citation,
            inputs_used=["size", "minimum_class", "facing"],
            verification=VerificationStatus.EXPERIMENTAL,
        )

    upstream = _pair("flange_upstream", 1.0)
    downstream = _pair("flange_downstream", 1.0)
    return make_result(
        symbol="flange_pair",
        value=2.0,
        kind="dimensionless",
        formula="pair = upstream flange + downstream flange + gasket + bolt set",
        substitutions={
            "size (NPS)": str(size),
            "class": str(int(pressure_class)),
            "facing": facing,
            "gasket type": gasket_type,
            "bolt set": f"{bolt_count} x M{bolt_diameter_mm:g}",
        },
        citation=citation,
        inputs_used=["size", "minimum_class", "facing", "gasket_type"],
        verification=VerificationStatus.EXPERIMENTAL,
        children=[upstream, downstream],
        issues=issues,
    )
