"""UW-12 joint-efficiency lookup tests."""

from __future__ import annotations

import pytest

from pemds.calc import joints


def test_type1_full_radiographic(editions):
    result = joints.joint_efficiency("1", "full", editions)
    assert result.value == pytest.approx(1.0)
    assert result.citation.clause == "UW-12"


def test_type1_no_radiography(editions):
    assert joints.joint_efficiency("1", "none", editions).value == pytest.approx(0.7)


def test_type2_spot(editions):
    assert joints.joint_efficiency("2", "spot", editions).value == pytest.approx(0.8)


def test_invalid_radiography_rejected(editions):
    with pytest.raises(ValueError, match="radiography must be one of"):
        joints.joint_efficiency("1", "sometimes", editions)


def test_unknown_combination_rejected(editions):
    with pytest.raises(ValueError, match="no UW-12 joint efficiency"):
        joints.joint_efficiency("9", "full", editions)
