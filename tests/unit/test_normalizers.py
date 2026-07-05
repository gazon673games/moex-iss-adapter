from __future__ import annotations

from datetime import datetime

import polars as pl
import pytest

from moex_iss_adapter.constants import CANONICAL_OHLCV_COLUMNS
from moex_iss_adapter.exceptions import MoexResponseFormatError
from moex_iss_adapter.normalizers import count_candle_rows, normalize_candles


def test_normalizes_candles_to_canonical_schema(sber_candles_response: dict) -> None:
    expected_rows = len(sber_candles_response["candles"]["data"])
    frame = normalize_candles(
        [sber_candles_response],
        engine="stock",
        market="shares",
        board="TQBR",
        symbol="SBER",
        timeframe="1d",
    )

    assert frame.columns == list(CANONICAL_OHLCV_COLUMNS)
    assert frame.height == expected_rows
    assert set(frame["source"].to_list()) == {"moex"}
    assert set(frame["exchange"].to_list()) == {"MOEX"}
    assert set(frame["engine"].to_list()) == {"stock"}
    assert set(frame["market"].to_list()) == {"shares"}
    assert set(frame["board"].to_list()) == {"TQBR"}
    assert set(frame["symbol"].to_list()) == {"SBER"}
    assert set(frame["timeframe"].to_list()) == {"1d"}
    assert "begin" not in frame.columns
    assert frame.schema["ts"] == pl.Datetime
    assert frame["open"].dtype == pl.Float64


def test_removes_exact_duplicate_rows(sber_candles_response: dict) -> None:
    expected_rows = len(sber_candles_response["candles"]["data"])
    duplicated = dict(sber_candles_response)
    duplicated["candles"] = dict(sber_candles_response["candles"])
    duplicated["candles"]["data"] = [
        *sber_candles_response["candles"]["data"],
        sber_candles_response["candles"]["data"][0],
    ]

    frame = normalize_candles(
        [duplicated],
        engine="stock",
        market="shares",
        board="TQBR",
        symbol="SBER",
        timeframe="1d",
    )

    assert frame.height == expected_rows


def test_empty_response_returns_empty_canonical_frame(empty_candles_response: dict) -> None:
    frame = normalize_candles(
        [empty_candles_response],
        engine="stock",
        market="shares",
        board="TQBR",
        symbol="SBER",
        timeframe="1d",
    )

    assert frame.columns == list(CANONICAL_OHLCV_COLUMNS)
    assert frame.height == 0


def test_normalized_candles_can_use_5m_timeframe(futures_candles_response: dict) -> None:
    frame = normalize_candles(
        [futures_candles_response],
        engine="futures",
        market="forts",
        board="RFUD",
        symbol="CRU6",
        timeframe="5m",
    )

    assert set(frame["timeframe"].to_list()) == {"5m"}
    assert set(frame["symbol"].to_list()) == {"CRU6"}
    assert "begin" not in frame.columns


def test_5m_timeframe_aggregates_1m_candles() -> None:
    response = {
        "candles": {
            "columns": ["begin", "open", "high", "low", "close", "volume", "value"],
            "data": [
                ["2026-07-01 10:00:00", 10.0, 11.0, 9.0, 10.5, 1.0, 100.0],
                ["2026-07-01 10:01:00", 10.5, 12.0, 10.0, 11.5, 2.0, 200.0],
                ["2026-07-01 10:04:00", 11.5, 13.0, 11.0, 12.5, 3.0, 300.0],
                ["2026-07-01 10:05:00", 12.5, 13.5, 12.0, 13.0, 4.0, 400.0],
            ],
        }
    }

    frame = normalize_candles(
        [response],
        engine="futures",
        market="forts",
        board="RFUD",
        symbol="CRU6",
        timeframe="5m",
    )

    assert frame.height == 2
    assert frame.get_column("ts").to_list() == [
        datetime(2026, 7, 1, 10, 0),
        datetime(2026, 7, 1, 10, 5),
    ]
    first = frame.row(0, named=True)
    assert first["open"] == 10.0
    assert first["high"] == 13.0
    assert first["low"] == 9.0
    assert first["close"] == 12.5
    assert first["volume"] == 6.0
    assert first["value"] == 600.0


def test_malformed_response_raises_response_format_error(malformed_response: dict) -> None:
    with pytest.raises(MoexResponseFormatError, match="missing table"):
        count_candle_rows(malformed_response)
