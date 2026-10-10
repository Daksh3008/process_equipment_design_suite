"""Calculation report engine (RP-1..RP-3).

Renders a :class:`ResultTree` as an HTML document and a PDF. Every row shows the
symbol, the value converted to the user's display units, the formula, the
substituted values, the full clause citation with edition, the verdict, the
margin and the verification status (RP-2). A liability disclaimer is always
printed (R-4).
"""

from __future__ import annotations

import html
from pathlib import Path

from pydantic import BaseModel

from ..core.result import Issue, Result, ResultTree, Verdict
from ..core.units import (
    UnitSystem,
    base_unit,
    display_unit,
    format_value,
    from_base,
    to_base,
)

DISCLAIMER = (
    "Tool-assisted calculation. The qualified engineer of record remains responsible "
    "for the design. Verify results against the licensed code edition before use."
)

_VERDICT_LABEL = {
    Verdict.PASS: "PASS",
    Verdict.FAIL: "FAIL",
    Verdict.WARN: "WARN",
    Verdict.NA: "-",
}

#: Input field units that can be converted to the user's display system.
_UNIT_KIND = {
    "mm": "length",
    "MPa": "pressure",
    "degC": "temperature",
    "kg": "mass",
    "N": "force",
}


def _display_input(value: object, unit: str, system: UnitSystem) -> str:
    kind = _UNIT_KIND.get(unit)
    if kind is None or not isinstance(value, (int, float)):
        return f"{value} {unit}".strip()
    shown = from_base(to_base(float(value), unit, kind), kind, system)
    return format_value(shown, display_unit(kind, system))


def input_rows(model: BaseModel, system: UnitSystem = UnitSystem.SI) -> list[tuple[str, str]]:
    """Return (label, value+unit) rows for a pack input model in *system* (IN-1, IN-3)."""
    rows: list[tuple[str, str]] = []
    for name, field in type(model).model_fields.items():
        raw_extra = field.json_schema_extra
        meta = raw_extra if isinstance(raw_extra, dict) else {}
        value = getattr(model, name)
        if value is None:
            continue
        unit = str(meta.get("unit", ""))
        label = str(meta.get("label", name))
        rows.append((label, _display_input(value, unit, system)))
    return rows


def result_rows(tree: ResultTree, system: UnitSystem = UnitSystem.SI) -> list[list[str]]:
    """Flatten the tree into report rows with display-unit values."""
    rows: list[list[str]] = []
    for result in tree.flatten():
        rows.append(
            [
                result.symbol,
                _format_result_value(result, system),
                _VERDICT_LABEL[result.verdict],
                "n/a" if result.margin is None else f"{result.margin:+.1%}",
                result.citation.label(),
                result.verification.value,
                result.formula,
            ]
        )
    return rows


def _format_result_value(result: Result, system: UnitSystem) -> str:
    if result.value is None:
        return "-"
    if result.kind == "dimensionless":
        return f"{result.value:.4g}"
    shown = from_base(result.value, result.kind, system)
    unit = display_unit(result.kind, system)
    return format_value(shown, unit)


def render_html(
    *,
    project_name: str,
    equipment_id: str,
    family: str,
    inputs: BaseModel,
    tree: ResultTree,
    system: UnitSystem = UnitSystem.SI,
) -> str:
    """Render the full calculation report as a standalone HTML document."""
    input_table = "\n".join(
        f"<tr><th>{html.escape(label)}</th><td>{html.escape(value)}</td></tr>"
        for label, value in input_rows(inputs, system)
    )
    header = ["Symbol", "Value", "Verdict", "Margin", "Citation", "Status", "Formula"]
    body = "\n".join(
        "<tr>"
        + "".join(f"<td>{html.escape(cell)}</td>" for cell in row)
        + "</tr>"
        for row in result_rows(tree, system)
    )
    trace = "\n".join(
        "<tr><td>{sym}</td><td>{formula}</td><td>{subs}</td></tr>".format(
            sym=html.escape(result.symbol),
            formula=html.escape(result.formula),
            subs=html.escape(
                ", ".join(f"{k}={v}" for k, v in result.substitutions.items())
            ),
        )
        for result in tree.flatten()
    )
    overall = tree.overall_verdict().value.upper()
    governing = tree.governing_case or "-"
    warnings_html = _warnings_html(tree)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>{html.escape(equipment_id)} calculation report</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 2rem; color: #1a1a1a; }}
h1 {{ font-size: 1.4rem; }} h2 {{ font-size: 1.1rem; margin-top: 1.5rem; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 0.5rem; }}
th, td {{ border: 1px solid #ccc; padding: 0.3rem 0.5rem; text-align: left; font-size: 0.85rem; vertical-align: top; }}
th {{ background: #f2f2f2; }}
.verdict {{ font-weight: bold; }}
.disclaimer {{ margin-top: 2rem; font-size: 0.8rem; color: #666; }}
</style></head><body>
<h1>Calculation report — {html.escape(equipment_id)}</h1>
<p>Project: {html.escape(project_name)} &middot; Family: {html.escape(family)} &middot;
Governing case: {html.escape(governing)} &middot;
Overall verdict: <span class="verdict">{overall}</span></p>
<h2>Inputs</h2>
<table>{input_table}</table>
<h2>Results</h2>
<table><thead><tr>{''.join(f'<th>{html.escape(h)}</th>' for h in header)}</tr></thead>
<tbody>{body}</tbody></table>
<h2>Formula trace</h2>
<table><thead><tr><th>Symbol</th><th>Formula</th><th>Substituted values</th></tr></thead>
<tbody>{trace}</tbody></table>
{warnings_html}
<p class="disclaimer">{html.escape(DISCLAIMER)}</p>
</body></html>"""


def render_pdf(
    *,
    project_name: str,
    equipment_id: str,
    family: str,
    inputs: BaseModel,
    tree: ResultTree,
    path: str | Path,
    system: UnitSystem = UnitSystem.SI,
) -> Path:
    """Render the calculation report as a PDF and return the written path."""
    from reportlab.lib.pagesizes import (
        A4,
    )
    from reportlab.lib.styles import (
        getSampleStyleSheet,
    )
    from reportlab.lib.units import (
        mm,
    )
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
    )

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(out), pagesize=A4, title=f"{equipment_id} calculation report")
    story = [
        Paragraph(f"Calculation report — {html.escape(equipment_id)}", styles["Title"]),
        Paragraph(
            f"Project: {html.escape(project_name)} &middot; Family: {html.escape(family)} "
            f"&middot; Governing case: {html.escape(tree.governing_case or '-')} "
            f"&middot; Overall verdict: <b>{tree.overall_verdict().value.upper()}</b>",
            styles["Normal"],
        ),
        Spacer(1, 6 * mm),
        Paragraph("Inputs", styles["Heading2"]),
    ]

    input_data = [["Field", "Value"]] + [list(row) for row in input_rows(inputs, system)]
    story.append(_table(input_data, [70 * mm, 90 * mm]))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph("Results", styles["Heading2"]))

    header = ["Symbol", "Value", "Verdict", "Margin", "Citation", "Status"]
    result_data = [header] + [row[:6] for row in result_rows(tree, system)]
    story.append(
        _table(
            result_data,
            [22 * mm, 30 * mm, 18 * mm, 18 * mm, 62 * mm, 20 * mm],
        )
    )

    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Formula trace", styles["Heading2"]))
    for result in tree.flatten():
        subs = ", ".join(f"{k}={v}" for k, v in result.substitutions.items())
        story.append(
            Paragraph(
                f"<b>{html.escape(result.symbol)}</b>: {html.escape(result.formula)}<br/>"
                f"<font size=8>{html.escape(subs)} &nbsp; [{html.escape(result.citation.label())}]</font>",
                styles["Normal"],
            )
        )
        story.append(Spacer(1, 2 * mm))

    issues = _unique_issues(tree)
    if issues:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("Warnings and notes", styles["Heading2"]))
        for issue in issues:
            basis = f" — {html.escape(issue.rationale)}" if issue.rationale else ""
            story.append(
                Paragraph(
                    f"[{issue.severity.value}] {html.escape(issue.message)}{basis}",
                    styles["Normal"],
                )
            )

    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(DISCLAIMER, styles["Italic"]))
    doc.build(story)
    return out


def _unique_issues(tree: ResultTree) -> list[Issue]:
    """Issues deduplicated by (severity, message, rationale)."""
    seen: dict[tuple[str, str, str | None], Issue] = {}
    for issue in tree.all_issues():
        seen.setdefault((issue.severity.value, issue.message, issue.rationale), issue)
    return list(seen.values())


def _warnings_html(tree: ResultTree) -> str:
    issues = _unique_issues(tree)
    if not issues:
        return ""
    rows = "\n".join(
        f"<tr><td>{html.escape(issue.severity.value)}</td><td>{html.escape(issue.message)}</td>"
        f"<td>{html.escape(issue.rationale or '')}</td></tr>"
        for issue in issues
    )
    return (
        "<h2>Warnings and notes</h2>"
        "<table><thead><tr><th>Severity</th><th>Message</th><th>Basis</th></tr></thead>"
        f"<tbody>{rows}</tbody></table>"
    )


def _table(data: list[list[str]], widths: list[float]) -> object:
    from reportlab.lib import (
        colors,
    )
    from reportlab.platypus import (
        Table,
        TableStyle,
    )

    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def base_unit_of(kind: str) -> str:
    """Expose the internal base unit for a quantity kind (used by tests)."""
    return base_unit(kind)


def render_csv(tree: ResultTree, system: UnitSystem = UnitSystem.SI) -> str:
    """Render the flattened result tree as CSV for external document systems (EXT-1)."""
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["Symbol", "Value", "Verdict", "Margin", "Citation", "Status", "Formula"])
    for row in result_rows(tree, system):
        writer.writerow(row)
    return buffer.getvalue()
