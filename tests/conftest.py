"""Shared test fixtures."""

from __future__ import annotations

import pytest

from pemds.core.calc import CalcContext
from pemds.core.registry import EditionRegistry
from pemds.data.materials import MaterialsDB


@pytest.fixture(scope="session")
def editions():
    return EditionRegistry.load_default().editions()


@pytest.fixture(scope="session")
def materials():
    return MaterialsDB.load_default()


@pytest.fixture()
def ctx(editions, materials):
    return CalcContext(editions=editions, materials=materials)
