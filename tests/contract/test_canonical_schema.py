from __future__ import annotations

from moex_iss_adapter.constants import (
    CANONICAL_OHLCV_COLUMNS,
    FORBIDDEN_NORMALIZED_TIMESTAMP_COLUMNS,
    FUTURES_METADATA_COLUMNS,
    UNIQUE_KEY_COLUMNS,
)
from moex_iss_adapter.metadata import normalize_futures_metadata
from moex_iss_adapter.normalizers import normalize_candles


def test_normalized_candles_have_exact_canonical_schema(sber_candles_response: dict) -> None:
    frame = normalize_candles(
        [sber_candles_response],
        engine="stock",
        market="shares",
        board="TQBR",
        symbol="SBER",
        timeframe="1d",
    )

    assert frame.columns == list(CANONICAL_OHLCV_COLUMNS)
    assert "ts" in frame.columns
    for forbidden_column in FORBIDDEN_NORMALIZED_TIMESTAMP_COLUMNS:
        assert forbidden_column not in frame.columns


def test_uniqueness_key_is_unique_for_normalized_fixture(sber_candles_response: dict) -> None:
    frame = normalize_candles(
        [sber_candles_response],
        engine="stock",
        market="shares",
        board="TQBR",
        symbol="SBER",
        timeframe="1d",
    )

    assert set(UNIQUE_KEY_COLUMNS).issubset(frame.columns)
    assert frame.height == frame.unique(subset=list(UNIQUE_KEY_COLUMNS)).height


def test_futures_candles_keep_canonical_schema(futures_candles_response: dict) -> None:
    frame = normalize_candles(
        [futures_candles_response],
        engine="futures",
        market="forts",
        board="RFUD",
        symbol="CNYRUBF",
        timeframe="1d",
    )

    assert frame.columns == list(CANONICAL_OHLCV_COLUMNS)
    assert frame.height == frame.unique(subset=list(UNIQUE_KEY_COLUMNS)).height
    assert "ts" in frame.columns
    for forbidden_column in FORBIDDEN_NORMALIZED_TIMESTAMP_COLUMNS:
        assert forbidden_column not in frame.columns


def test_futures_metadata_has_stable_schema(futures_securities_response: dict) -> None:
    frame = normalize_futures_metadata(futures_securities_response)

    assert frame.columns == list(FUTURES_METADATA_COLUMNS)
    assert set(frame.columns).isdisjoint({"open", "high", "low", "close", "volume", "value"})
