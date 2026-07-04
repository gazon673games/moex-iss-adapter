from __future__ import annotations

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


def test_malformed_response_raises_response_format_error(malformed_response: dict) -> None:
    with pytest.raises(MoexResponseFormatError, match="missing table"):
        count_candle_rows(malformed_response)
