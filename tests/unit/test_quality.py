from __future__ import annotations

import polars as pl

from moex_iss_adapter.normalizers import normalize_candles
from moex_iss_adapter.quality import validate_candles


def _normalized(response: dict) -> pl.DataFrame:
    return normalize_candles(
        [response],
        engine="stock",
        market="shares",
        board="TQBR",
        symbol="SBER",
        timeframe="1d",
    )


def test_quality_passes_for_valid_candles(sber_candles_response: dict) -> None:
    report = validate_candles(_normalized(sber_candles_response))

    assert report.passed
    assert report.row_count == len(sber_candles_response["candles"]["data"])
    assert report.duplicate_count == 0
    assert report.min_ts is not None
    assert report.max_ts is not None
    assert report.issues == []


def test_quality_reports_duplicate_key(sber_candles_response: dict) -> None:
    frame = _normalized(sber_candles_response)
    frame = pl.concat([frame, frame.head(1)])

    report = validate_candles(frame)

    assert not report.passed
    assert report.duplicate_count == 1
    assert any("Duplicate rows" in issue for issue in report.issues)


def test_quality_reports_ohlc_and_volume_violations(sber_candles_response: dict) -> None:
    frame = _normalized(sber_candles_response).with_columns(
        pl.when(pl.arange(0, pl.len()) == 0).then(100.0).otherwise(pl.col("high")).alias("high"),
        pl.when(pl.arange(0, pl.len()) == 0).then(-1.0).otherwise(pl.col("volume")).alias("volume"),
    )

    report = validate_candles(frame)

    assert not report.passed
    assert any("high must be greater than or equal to open" in issue for issue in report.issues)
    assert any("volume must be greater than or equal to 0" in issue for issue in report.issues)


def test_quality_reports_empty_frame(empty_candles_response: dict) -> None:
    report = validate_candles(_normalized(empty_candles_response))

    assert not report.passed
    assert report.row_count == 0
    assert "DataFrame is empty" in report.issues


def test_quality_reports_unsorted_timestamps(sber_candles_response: dict) -> None:
    report = validate_candles(_normalized(sber_candles_response).reverse())

    assert not report.passed
    assert "Rows are not sorted by ts" in report.issues


def test_quality_reports_null_timestamps_without_sorting_error(sber_candles_response: dict) -> None:
    frame = _normalized(sber_candles_response).with_columns(pl.lit(None).alias("ts"))

    report = validate_candles(frame)

    assert not report.passed
    assert "Column ts contains null values" in report.issues
    assert "Rows are not sorted by ts" not in report.issues
