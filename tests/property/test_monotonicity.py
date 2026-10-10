"""Property-based tests (VAL-3)."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from pemds.calc import shell
from pemds.core.registry import EditionRegistry

EDITIONS = EditionRegistry.load_default().editions()

_settings = settings(max_examples=80, deadline=None)
_floats = st.floats


@_settings
@given(
    p1=_floats(min_value=1.0e4, max_value=4.0e6),
    delta=_floats(min_value=1.0e4, max_value=1.0e6),
    r=_floats(min_value=0.2, max_value=3.0),
    s=_floats(min_value=9.0e7, max_value=2.0e8),
)
def test_thickness_increases_with_pressure(p1, delta, r, s):
    t1 = shell.circumferential_thickness(p1, r, s, 1.0, EDITIONS).value
    t2 = shell.circumferential_thickness(p1 + delta, r, s, 1.0, EDITIONS).value
    assert t2 > t1


@_settings
@given(
    p=_floats(min_value=1.0e4, max_value=4.0e6),
    r=_floats(min_value=0.2, max_value=3.0),
    s1=_floats(min_value=9.0e7, max_value=1.5e8),
    delta=_floats(min_value=1.0e6, max_value=5.0e7),
)
def test_thickness_decreases_with_allowable_stress(p, r, s1, delta):
    t1 = shell.circumferential_thickness(p, r, s1, 1.0, EDITIONS).value
    t2 = shell.circumferential_thickness(p, r, s1 + delta, 1.0, EDITIONS).value
    assert t2 < t1


@_settings
@given(
    t=_floats(min_value=0.003, max_value=0.05),
    r=_floats(min_value=0.2, max_value=3.0),
    s=_floats(min_value=9.0e7, max_value=2.0e8),
)
def test_mawp_increases_with_thickness(t, r, s):
    p1 = shell.circumferential_mawp(t, r, s, 1.0, EDITIONS).value
    p2 = shell.circumferential_mawp(t * 1.1, r, s, 1.0, EDITIONS).value
    assert p2 > p1


def test_result_is_pure():
    args = (1.0e6, 1.0, 138.0e6, 1.0, EDITIONS)
    first = shell.circumferential_thickness(*args)
    second = shell.circumferential_thickness(*args)
    assert first.value == second.value
    assert first.substitutions == second.substitutions
