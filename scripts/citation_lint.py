"""Citation and copyright lint (CIT-2, CIT-4).

Three gates, runnable from CI:

1. Every data file carries a complete provenance header.
2. Every calculation that returns a :class:`~pemds.core.result.Result` carries
   clause/source metadata (``@provable``).
3. No data file embeds a long string literal, which would suggest copied
   normative prose or a table reproduction.

Run as ``python scripts/citation_lint.py [repo_root]``; exits non-zero on
violations. The check functions are importable so tests can seed violations.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REQUIRED_KEYS = ("source", "edition", "clause", "licence", "transcribed_on", "checked_by")
_CALC_MODULES = (
    "pemds.calc.shell",
    "pemds.calc.heads",
    "pemds.calc.flat",
    "pemds.calc.joints",
    "pemds.calc.minimums",
    "pemds.calc.mawp",
    "pemds.calc.hydrotest",
    "pemds.calc.external",
    "pemds.calc.openings",
    "pemds.calc.pipe",
    "pemds.calc.rings",
    "pemds.calc.weights",
    "pemds.calc.flange",
    "pemds.calc.tank",
    "pemds.calc.tubesheet",
    "pemds.calc.column",
    "pemds.calc.pump",
    "pemds.data.fluid_properties",
)
_MAX_STRING_LENGTH = 400


def check_data_provenance(root: Path) -> list[str]:
    violations: list[str] = []
    data_root = root / "src" / "pemds" / "data"
    for path in sorted(data_root.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            violations.append(f"{path}: invalid JSON: {exc}")
            continue
        provenance = payload.get("provenance") if isinstance(payload, dict) else None
        if not isinstance(provenance, dict):
            violations.append(f"{path}: missing provenance header")
            continue
        for key in _REQUIRED_KEYS:
            if not str(provenance.get(key, "")).strip():
                violations.append(f"{path}: provenance header missing {key!r}")
    return violations


def check_data_strings(root: Path) -> list[str]:
    violations: list[str] = []
    data_root = root / "src" / "pemds" / "data"
    for path in sorted(data_root.rglob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for location, text in _iter_strings(payload, path.name):
            if len(text) > _MAX_STRING_LENGTH:
                violations.append(
                    f"{path}: long string literal ({len(text)} chars) at {location} "
                    "may be reproduced normative text"
                )
    return violations


def _iter_strings(node: object, label: str, path: str = "$"):
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from _iter_strings(value, label, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _iter_strings(value, label, f"{path}[{index}]")


def check_calc_citations() -> list[str]:
    violations: list[str] = []
    import importlib
    import typing

    from pemds.core.result import Result

    for module_name in _CALC_MODULES:
        module = importlib.import_module(module_name)
        for name, obj in vars(module).items():
            if name.startswith("_"):
                continue
            if not callable(obj) or not hasattr(obj, "__code__"):
                continue
            if obj.__module__ != module.__name__:
                continue
            try:
                hints = typing.get_type_hints(obj)
            except Exception as exc:  # noqa: BLE001 - lint reports, never crashes
                violations.append(f"{module_name}.{name}: could not resolve type hints ({exc})")
                continue
            if hints.get("return") is not Result:
                continue
            meta = getattr(obj, "__pemds_meta__", None)
            if meta is None:
                violations.append(
                    f"{module_name}.{name}: returns Result but has no @provable clause metadata"
                )
            elif not meta.source_tag:
                violations.append(f"{module_name}.{name}: @provable has an empty source tag")
    return violations


def check_python_placeholder_text(root: Path) -> list[str]:
    """Flag TODO/FIXME markers in delivered source (law 9: complete output)."""
    violations: list[str] = []
    code_roots = [root / "src"]
    if (root / "scripts").is_dir():
        code_roots.append(root / "scripts")
    for src in code_roots:
        for path in sorted(src.rglob("*.py")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                marker = line.strip()
                if marker.startswith("#") and ("TODO" in marker or "FIXME" in marker):
                    violations.append(f"{path}:{number}: placeholder marker {marker!r}")
    return violations


def run(root: Path) -> list[str]:
    return (
        check_data_provenance(root)
        + check_data_strings(root)
        + check_calc_citations()
        + check_python_placeholder_text(root)
    )


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    root = Path(args[0]) if args else Path.cwd()
    violations = run(root)
    if violations:
        print("citation lint FAILED:")
        for violation in violations:
            print(f"  - {violation}")
        return 1
    print("citation lint passed")
    return 0


if __name__ == "__main__":  # pragma: no cover - script entry point
    sys.exit(main())
