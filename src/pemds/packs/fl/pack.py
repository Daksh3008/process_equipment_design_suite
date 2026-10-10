"""Flange/nozzle pack orchestration (FR-FL, FL-1..FL-3).

Selects a B16.5 pressure class for the design condition, checks the bolted joint
(target torque, gasket seating vs operating, bolt area) and builds a per-size
nozzle schedule with the mating flange pair. All user units are converted to
internal SI at this boundary.

Every result here is EXPERIMENTAL: the rating, bolting and gasket tables are
provisional demonstration sets (``checked_by`` contains ``UNVERIFIED``), so the
data policy forbids labelling them verified (VAL-2).
"""

from __future__ import annotations

import math

from pydantic import BaseModel

from ...calc import flange as flange_calc
from ...calc.common import make_result, propagate_experimental_children
from ...core.calc import CalcContext
from ...core.result import Issue, Result, ResultTree, Severity
from ...core.units import format_value, to_base
from ...core.validation import IssueCollector
from .model import ConnectionInput, FlangeInputs


class FlangePack:
    """The flanges and nozzles equipment pack (ASME B16.5 / B16.20)."""

    family = "flange"
    Input = FlangeInputs

    def validate(self, inputs: BaseModel) -> list[Issue]:
        if not isinstance(inputs, FlangeInputs):
            raise TypeError(f"expected FlangeInputs, got {type(inputs).__name__}")
        collector = IssueCollector()
        sizes = flange_calc.known_sizes()
        groups = flange_calc.known_material_groups()
        classes = flange_calc.known_pressure_classes()
        gaskets = flange_calc.known_gasket_types()

        if not inputs.tag.strip():
            collector.error("equipment tag must not be blank", field="tag")
        if inputs.size not in sizes:
            collector.error(
                f"nominal size {inputs.size!r} is not tabulated; available: {list(sizes)}",
                field="size",
            )
        if inputs.material_group not in groups:
            collector.error(
                f"material group {inputs.material_group!r} is not tabulated; "
                f"available: {list(groups)}",
                field="material_group",
            )
        if inputs.design_pressure_mpa <= 0:
            collector.error("design pressure must be > 0", field="design_pressure_mpa")
        if not math.isfinite(inputs.design_temperature_c):
            collector.error("design temperature must be finite", field="design_temperature_c")
        else:
            low, high = flange_calc.rating_temperature_range()
            if not low <= inputs.design_temperature_c <= high:
                collector.error(
                    f"design temperature must lie within the tabulated rating range "
                    f"{low:g}..{high:g} degC",
                    field="design_temperature_c",
                )
        if inputs.minimum_class is not None and inputs.minimum_class not in classes:
            collector.error(
                f"minimum class {inputs.minimum_class} is not tabulated; available: {list(classes)}",
                field="minimum_class",
            )
        if inputs.gasket_type not in gaskets:
            collector.error(
                f"gasket type {inputs.gasket_type!r} is not tabulated; "
                f"available: {list(gaskets)}",
                field="gasket_type",
            )
        if not 0.0 < inputs.nut_factor_k <= 1.0:
            collector.error("nut factor must lie in (0, 1]", field="nut_factor_k")

        seen_tags: set[str] = set()
        for connection in inputs.connections:
            if not connection.tag.strip():
                collector.error("connection tag must not be blank", field="connections")
            elif connection.tag in seen_tags:
                collector.error(
                    f"duplicate connection tag {connection.tag!r}", field="connections"
                )
            seen_tags.add(connection.tag)
            if connection.size not in sizes:
                collector.error(
                    f"connection {connection.tag}: size {connection.size!r} is not tabulated; "
                    f"available: {list(sizes)}",
                    field="connections",
                )
            if connection.minimum_class is not None and connection.minimum_class not in classes:
                collector.error(
                    f"connection {connection.tag}: minimum class {connection.minimum_class} "
                    f"is not tabulated; available: {list(classes)}",
                    field="connections",
                )
        return collector.issues

    def calculate(self, inputs: BaseModel, ctx: CalcContext) -> ResultTree:
        if not isinstance(inputs, FlangeInputs):
            raise TypeError(f"expected FlangeInputs, got {type(inputs).__name__}")
        collector = IssueCollector()
        for issue in self.validate(inputs):
            if issue.severity is Severity.ERROR:
                collector.error(issue.message, issue.field)
        collector.raise_if_errors()

        editions = ctx.editions
        pressure = to_base(inputs.design_pressure_mpa, "MPa", "pressure")
        temperature = inputs.design_temperature_c

        tree = ResultTree(name=inputs.tag, governing_case="design")

        # --- FL-1: rating selection -------------------------------------------
        selection = flange_calc.select_class(
            inputs.size,
            inputs.material_group,
            pressure,
            temperature,
            editions,
            minimum_class=inputs.minimum_class,
        )
        selected_rating = _selected_rating(selection)
        selected_class = int(selection.value) if selection.value is not None else 0
        tree.add(
            make_result(
                symbol="flange_rating",
                value=_rating_pa(selected_rating),
                kind="pressure",
                formula="P_rating >= P_design; class = lowest qualifying B16.5 class",
                substitutions={
                    "size (NPS)": inputs.size,
                    "material group": inputs.material_group,
                    "design pressure": format_value(pressure, "Pa"),
                    "temperature": f"{temperature:g} degC",
                    "selected class": str(selected_class),
                    "rating at selected class": format_value(_rating_pa(selected_rating), "Pa"),
                },
                citation=selected_rating.citation,
                inputs_used=[
                    "size",
                    "material_group",
                    "design_pressure_mpa",
                    "design_temperature_c",
                    "minimum_class",
                ],
                verdict=selection.verdict,
                margin=selection.margin,
                verification=selection.verification,
                children=[selection],
                issues=list(selection.issues),
            )
        )

        # --- FL-2: bolt/gasket selection + target torque ----------------------
        gasket_type = inputs.gasket_type
        contact_width = (
            to_base(inputs.gasket_contact_width_mm, "mm", "length")
            if inputs.gasket_contact_width_mm is not None
            else flange_calc.gasket_contact_width_m(gasket_type)
        )
        effective_width = flange_calc.effective_gasket_width_m(contact_width)
        gasket_m, gasket_y_pa = flange_calc.gasket_factors(gasket_type)
        bolt_count, bolt_diameter_m, bolt_area_m2, _bolt_material = flange_calc.bolt_spec(
            inputs.size, selected_class
        )
        tree.add(
            flange_calc.bolt_up_check(
                pressure,
                to_base(inputs.gasket_mean_diameter_mm, "mm", "length"),
                effective_width,
                gasket_m,
                gasket_y_pa,
                bolt_count,
                bolt_area_m2,
                bolt_diameter_m,
                to_base(inputs.bolt_allowable_stress_mpa, "MPa", "pressure"),
                inputs.nut_factor_k,
                editions,
            )
        )

        # --- FL-3: nozzle-size schedule ---------------------------------------
        for connection in inputs.connections:
            tree.add(self._connection(connection, inputs, pressure, editions))

        propagate_experimental_children(tree)
        return tree

    def _connection(
        self,
        connection: ConnectionInput,
        inputs: FlangeInputs,
        pressure: float,
        editions,
    ) -> Result:
        selection = flange_calc.select_class(
            connection.size,
            inputs.material_group,
            pressure,
            inputs.design_temperature_c,
            editions,
            minimum_class=connection.minimum_class,
        )
        selected_rating = _selected_rating(selection)
        selected_class = int(selection.value) if selection.value is not None else 0
        bolt_count, bolt_diameter_m, _bolt_area_m2, bolt_material = flange_calc.bolt_spec(
            connection.size, selected_class
        )
        pair = flange_calc.mating_flange_pair(
            connection.size,
            selected_class,
            inputs.facing,
            inputs.gasket_type,
            bolt_count,
            bolt_diameter_m * 1000.0,
            editions,
        )
        return make_result(
            symbol=f"connection_{connection.tag}",
            value=selection.value,
            kind="dimensionless",
            formula="connection = size -> selected class -> mating flange pair",
            substitutions={
                "tag": connection.tag,
                "service": connection.service or "-",
                "size (NPS)": connection.size,
                "material group": inputs.material_group,
                "selected class": str(selected_class),
                "rating at selected class": format_value(_rating_pa(selected_rating), "Pa"),
                "bolt set": f"{bolt_count} x M{bolt_diameter_m * 1000.0:g}",
                "bolt material": bolt_material,
            },
            citation=selected_rating.citation,
            inputs_used=[
                "connections",
                "size",
                "material_group",
                "design_pressure_mpa",
                "design_temperature_c",
                "facing",
                "gasket_type",
            ],
            verdict=selection.verdict,
            margin=selection.margin,
            verification=selection.verification,
            children=[selection, pair],
            issues=list(selection.issues),
        )


def _selected_rating(selection: Result) -> Result:
    if selection.value is None:
        raise ValueError("class selection produced no class")
    wanted = str(int(selection.value))
    for child in selection.children:
        if child.substitutions.get("class") == wanted:
            return child
    raise ValueError(f"class selection did not report a rating for class {wanted}")


def _rating_pa(rating: Result) -> float:
    """The numeric rating from a rating result, failing loudly if it is absent."""
    value = rating.value
    if value is None:
        raise ValueError(f"{rating.symbol}: rating lookup produced no value")
    return value
