from __future__ import annotations

import pytest

from moex_iss_adapter.constants import TIMEFRAME_TO_MOEX_INTERVAL
from moex_iss_adapter.endpoints import (
    build_boards_path,
    build_candles_path,
    build_candles_request,
    build_full_url,
    build_global_securities_search_path,
    build_global_security_details_path,
    build_market_candles_path,
    build_market_securities_path,
    build_securities_columns_path,
    moex_interval_for_timeframe,
)
from moex_iss_adapter.exceptions import MoexIssAdapterError


def test_builds_board_specific_candles_path() -> None:
    assert (
        build_candles_path("stock", "shares", "TQBR", "SBER")
        == "/engines/stock/markets/shares/boards/TQBR/securities/SBER/candles.json"
    )


def test_builds_candles_request_params() -> None:
    path, params = build_candles_request(
        engine="stock",
        market="shares",
        board="TQBR",
        security="SBER",
        timeframe="1d",
        from_date="2023-01-01",
        till_date="2023-12-31",
        start=0,
    )

    assert path.endswith("/boards/TQBR/securities/SBER/candles.json")
    assert params == {
        "from": "2023-01-01",
        "till": "2023-12-31",
        "interval": 24,
        "start": 0,
    }


def test_timeframe_mapping_is_centralized() -> None:
    assert TIMEFRAME_TO_MOEX_INTERVAL == {
        "1m": 1,
        "5m": 1,
        "10m": 10,
        "1h": 60,
        "1d": 24,
        "1w": 7,
        "1mo": 31,
        "1q": 4,
    }
    assert moex_interval_for_timeframe("1d") == 24
    assert moex_interval_for_timeframe("5m") == 1


def test_rejects_unknown_timeframe() -> None:
    with pytest.raises(MoexIssAdapterError, match="Unsupported timeframe"):
        moex_interval_for_timeframe("2d")


def test_build_full_url_uses_base_url() -> None:
    assert (
        build_full_url("/engines.json", base_url="https://iss.moex.com/iss/")
        == "https://iss.moex.com/iss/engines.json"
    )


def test_builds_futures_securities_endpoint() -> None:
    assert (
        build_market_securities_path("futures", "forts")
        == "/engines/futures/markets/forts/securities.json"
    )


def test_builds_futures_securities_columns_endpoint() -> None:
    assert (
        build_securities_columns_path("futures", "forts")
        == "/engines/futures/markets/forts/securities/columns.json"
    )


def test_builds_futures_boards_endpoint() -> None:
    assert build_boards_path("futures", "forts") == "/engines/futures/markets/forts/boards.json"


def test_builds_futures_market_level_candles_endpoint() -> None:
    assert (
        build_market_candles_path("futures", "forts", "CNYRUBF")
        == "/engines/futures/markets/forts/securities/CNYRUBF/candles.json"
    )


def test_builds_global_security_search_and_details_endpoints() -> None:
    assert build_global_securities_search_path() == "/securities.json"
    assert build_global_security_details_path("CRH5") == "/securities/CRH5.json"


def test_builds_futures_board_specific_candles_request() -> None:
    path, params = build_candles_request(
        engine="futures",
        market="forts",
        board="RFUD",
        security="CNYRUBF",
        timeframe="1d",
        from_date="2023-01-10",
        till_date="2023-01-20",
        start=0,
    )

    assert path == "/engines/futures/markets/forts/boards/RFUD/securities/CNYRUBF/candles.json"
    assert params["interval"] == 24


def test_builds_currency_securities_endpoint() -> None:
    assert (
        build_market_securities_path("currency", "selt")
        == "/engines/currency/markets/selt/securities.json"
    )


def test_builds_currency_boards_endpoint() -> None:
    assert build_boards_path("currency", "selt") == "/engines/currency/markets/selt/boards.json"


def test_builds_currency_market_level_candles_endpoint() -> None:
    assert (
        build_market_candles_path("currency", "selt", "CNY000000TOD")
        == "/engines/currency/markets/selt/securities/CNY000000TOD/candles.json"
    )


def test_builds_currency_board_specific_candles_request() -> None:
    path, params = build_candles_request(
        engine="currency",
        market="selt",
        board="CETS",
        security="CNY000000TOD",
        timeframe="1d",
        from_date="2023-01-10",
        till_date="2023-01-20",
        start=0,
    )

    assert path == "/engines/currency/markets/selt/boards/CETS/securities/CNY000000TOD/candles.json"
    assert params["interval"] == 24
