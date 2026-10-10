"""Result-tree semantics tests."""

from __future__ import annotations

from pemds.core.provenance import Citation
from pemds.core.result import (
    Issue,
    Result,
    ResultTree,
    Severity,
    Verdict,
    worst_verdict,
)

_CITE = Citation("ASME BPVC Section VIII, Division 1", "2023", "UG-27(c)(1)", "S1")


def _result(symbol: str, verdict: Verdict) -> Result:
    return Result(
        symbol=symbol,
        value=1.0,
        unit="m",
        kind="length",
        formula="t = 1",
        substitutions={},
        citation=_CITE,
        verdict=verdict,
    )


def test_overall_verdict_priority():
    tree = ResultTree(name="x")
    tree.add(_result("a", Verdict.PASS))
    assert tree.overall_verdict() is Verdict.PASS
    tree.add(_result("b", Verdict.WARN))
    assert tree.overall_verdict() is Verdict.WARN
    tree.add(_result("c", Verdict.FAIL))
    assert tree.overall_verdict() is Verdict.FAIL


def test_all_na_is_na():
    tree = ResultTree(name="x", roots=[_result("a", Verdict.NA)])
    assert tree.overall_verdict() is Verdict.NA


def test_flatten_includes_children():
    parent = _result("p", Verdict.PASS)
    parent.add(_result("c1", Verdict.PASS))
    parent.add(_result("c2", Verdict.FAIL))
    tree = ResultTree(name="x", roots=[parent])
    assert [r.symbol for r in tree.flatten()] == ["p", "c1", "c2"]


def test_issues_are_collected():
    parent = _result("p", Verdict.WARN)
    parent.issues.append(Issue(Severity.WARNING, "watch out", field="p"))
    tree = ResultTree(name="x", roots=[parent])
    assert len(tree.all_issues()) == 1
    assert tree.all_issues()[0].field == "p"


def test_to_dict_round_trips_structure():
    tree = ResultTree(name="x", roots=[_result("p", Verdict.PASS)], governing_case="design")
    payload = tree.to_dict()
    assert payload["overall_verdict"] == "pass"
    assert payload["governing_case"] == "design"
    assert payload["roots"][0]["citation"]["clause"] == "UG-27(c)(1)"


def test_worst_verdict():
    assert worst_verdict([Verdict.PASS, Verdict.WARN]) is Verdict.WARN
    assert worst_verdict([]) is Verdict.NA
