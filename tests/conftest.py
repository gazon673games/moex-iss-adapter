from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture()
def sber_candles_response() -> dict[str, Any]:
    return load_fixture("moex_candles_sber_tqbr_1d_sample.json")


@pytest.fixture()
def empty_candles_response() -> dict[str, Any]:
    return load_fixture("moex_empty_candles_response.json")


@pytest.fixture()
def malformed_response() -> dict[str, Any]:
    return load_fixture("moex_malformed_response.json")


@pytest.fixture()
def futures_securities_response() -> dict[str, Any]:
    return load_fixture("moex_futures_securities_sample.json")


@pytest.fixture()
def futures_boards_response() -> dict[str, Any]:
    return load_fixture("moex_futures_boards_sample.json")


@pytest.fixture()
def futures_candles_response() -> dict[str, Any]:
    return load_fixture("moex_futures_candles_sample.json")


@pytest.fixture()
def empty_futures_securities_response() -> dict[str, Any]:
    return load_fixture("moex_futures_empty_securities_response.json")


@pytest.fixture()
def futures_securities_empty_response() -> dict[str, Any]:
    return load_fixture("moex_futures_securities_empty.json")


@pytest.fixture()
def futures_securities_malformed_response() -> dict[str, Any]:
    return load_fixture("moex_futures_securities_malformed.json")
