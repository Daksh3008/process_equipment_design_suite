"""Regenerate the FR-CC component identity snapshot (CC-1, CC-10).

The identity rows (name, CAS, formula, molar mass, aliases) are extracted from
the pinned CoolProp release's fluid metadata, which derives from the NIST
Chemistry WebBook (public domain) and REFPROP. The output is a static,
provenance-stamped data file so the application itself stays offline-first
(NFR-8): CoolProp is only needed to *regenerate* this file, not to read it.

Run::

    python scripts/generate_component_identity.py

The date and CoolProp version are recorded in the provenance header, so the
snapshot is reproducible and auditable (CIT-3).
"""

from __future__ import annotations

import datetime as _dt
import json
import math
import re
import sys
from pathlib import Path

import CoolProp
import CoolProp.CoolProp as CP

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TARGET = _REPO_ROOT / "src" / "pemds" / "data" / "components" / "identities.json"

#: ``H_{2}O_{1}`` -> ``H2O``: strip the LaTeX subscript braces and a trailing 1.
_SUBSCRIPT = re.compile(r"_\{(\d+)\}")


def _plain_formula(raw: str) -> str:
    """Convert CoolProp's LaTeX-style formula to a conventional plain formula."""
    text = _SUBSCRIPT.sub(lambda m: "" if m.group(1) == "1" else m.group(1), raw)
    return text.strip()


def _clean_aliases(raw: str, name: str) -> list[str]:
    """Case-insensitive, order-preserving de-duplication of a comma list."""
    seen: set[str] = set()
    out: list[str] = []
    for item in raw.split(","):
        token = item.strip()
        if not token:
            continue
        folded = token.casefold()
        if folded == name.casefold() or folded in seen:
            continue
        seen.add(folded)
        out.append(token)
    return out


def build() -> dict:
    rows = []
    errors: list[str] = []
    missing_cas: list[str] = []
    missing_formula: list[str] = []
    for key in CP.FluidsList():
        try:
            name = CP.get_fluid_param_string(key, "name")
        except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
            errors.append(f"{key}: name metadata failed: {exc}")
            name = ""
        if not (name or "").strip():
            errors.append(f"{key}: no display name available")
        try:
            cas = CP.get_fluid_param_string(key, "CAS").strip()
        except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
            errors.append(f"{key}: CAS metadata failed: {exc}")
            cas = ""
        if not cas:
            missing_cas.append(key)
        try:
            formula = _plain_formula(CP.get_fluid_param_string(key, "formula"))
        except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
            errors.append(f"{key}: formula metadata failed: {exc}")
            formula = ""
        if not formula:
            missing_formula.append(key)
        try:
            aliases = _clean_aliases(CP.get_fluid_param_string(key, "aliases"), name)
        except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
            errors.append(f"{key}: aliases metadata failed: {exc}")
            aliases = []
        try:
            molar_mass_kg_mol = float(CP.PropsSI("M", "T", 298.15, "P", 101325.0, key))
        except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
            errors.append(f"{key}: molar mass evaluation failed: {exc}")
            molar_mass_kg_mol = 0.0
        if not math.isfinite(molar_mass_kg_mol) or molar_mass_kg_mol <= 0:
            errors.append(f"{key}: no positive molar mass")
        rows.append(
            {
                "key": key,
                "name": name,
                "cas": cas,
                "formula": formula,
                "aliases": aliases,
                "molar_mass_kg_mol": molar_mass_kg_mol,
            }
        )
    if errors:
        raise RuntimeError(
            "component identity snapshot incomplete; refusing to write:\n" + "\n".join(errors)
        )
    rows.sort(key=lambda row: row["key"].casefold())
    provenance = {
        "source": "CoolProp fluid metadata (built on NIST Chemistry WebBook and REFPROP)",
        "edition": CoolProp.__version__,
        "clause": "fluid identity metadata (name, CAS, formula, molar mass)",
        "licence": (
            "CoolProp is MIT-licensed; NIST Chemistry WebBook data is a US Government "
            "work. Identity metadata only; no normative standard content is reproduced."
        ),
        "transcribed_on": _dt.datetime.now(tz=_dt.UTC).date().isoformat(),
        "checked_by": (
            "UNVERIFIED - CoolProp auto-generated snapshot; identity metadata has not "
            "been independently reviewed against NIST WebBook"
        ),
        "source_tag": "S22",
    }
    if missing_cas:
        note = ", ".join(sorted(missing_cas))
        provenance["note"] = f"no CAS on {note[:200]}"
    if missing_formula:
        note = ", ".join(sorted(missing_formula))
        provenance["note_formula_missing"] = f"no formula on {note[:200]}"
    return {"provenance": provenance, "components": rows}


def main() -> int:
    try:
        payload = build()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    _TARGET.parent.mkdir(parents=True, exist_ok=True)
    _TARGET.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {_TARGET} ({len(payload['components'])} components, CoolProp {CoolProp.__version__})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
