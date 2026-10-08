"""Structured data quality checks for canonical OHLCV candles."""

from __future__ import annotations

from datetime import datetime

import polars as pl

from moex_iss_adapter.constants import (
    CANONICAL_OHLCV_COLUMNS,
    DEFAULT_EXCHANGE,
    DEFAULT_FUTURES_ENGINE,
    DEFAULT_FUTURES_MARKET,
    DEFAULT_SOURCE,
    FUTURES_METADATA_COLUMNS,
    FUTURES_METADATA_UNIQUE_KEY_COLUMNS,
    UNIQUE_KEY_COLUMNS,
)
from moex_iss_adapter.models import MetadataQualityReport, QualityReport


def _null_count(frame: pl.DataFrame, column: str) -> int:
    return int(frame.select(pl.col(column).is_null().sum()).item())


def _violation_count(frame: pl.DataFrame, expression: pl.Expr) -> int:
    return int(frame.select(expression.fill_null(False).sum()).item())


def _min_max_ts(frame: pl.DataFrame) -> tuple[datetime | None, datetime | None]:
    if "ts" not in frame.columns or frame.is_empty():
        return None, None
    result = frame.select(pl.col("ts").min().alias("min_ts"), pl.col("ts").max().alias("max_ts"))
    row = result.row(0, named=True)
    return row["min_ts"], row["max_ts"]


def validate_candles(frame: pl.DataFrame) -> QualityReport:
    """Run canonical OHLCV quality checks and return a structured report."""

    issues: list[str] = []
    row_count = frame.height

    if row_count == 0:
        issues.append("DataFrame is empty")

    missing_columns = [column for column in CANONICAL_OHLCV_COLUMNS if column not in frame.columns]
    if missing_columns:
        issues.append(f"Missing required columns: {', '.join(missing_columns)}")
        return QualityReport(
            passed=False,
            row_count=row_count,
            min_ts=None,
            max_ts=None,
            duplicate_count=0,
            issues=issues,
        )

    min_ts, max_ts = _min_max_ts(frame)

    ts_nulls = _null_count(frame, "ts")
    if ts_nulls > 0:
        issues.append("Column ts contains null values")

    for column in ("open", "high", "low", "close"):
        if not frame[column].dtype.is_numeric():
            issues.append(f"Column {column} must be numeric")
            continue
        if frame.select((~pl.col(column).is_finite()).sum()).item():
            issues.append(f"Column {column} contains non-finite values")
        nulls = _null_count(frame, column)
        if nulls > 0:
            issues.append(f"Column {column} contains {nulls} null values")

    duplicate_count = row_count - frame.unique(subset=list(UNIQUE_KEY_COLUMNS)).height
    if duplicate_count > 0:
        issues.append(
            "Duplicate rows found by key source + exchange + board + symbol + timeframe + ts: "
            f"{duplicate_count}"
        )

    if ts_nulls == 0 and not frame.get_column("ts").is_sorted():
        issues.append("Rows are not sorted by ts")

    if any(not frame[column].dtype.is_numeric() for column in ("open", "high", "low", "close")):
        return QualityReport(
            passed=False,
            row_count=row_count,
            min_ts=min_ts,
            max_ts=max_ts,
            duplicate_count=duplicate_count,
            issues=issues,
        )

    comparisons = (
        ("high must be greater than or equal to open", pl.col("high") < pl.col("open")),
        ("high must be greater than or equal to close", pl.col("high") < pl.col("close")),
        ("high must be greater than or equal to low", pl.col("high") < pl.col("low")),
        ("low must be less than or equal to open", pl.col("low") > pl.col("open")),
        ("low must be less than or equal to close", pl.col("low") > pl.col("close")),
        ("open must be greater than 0", pl.col("open") <= 0),
        ("close must be greater than 0", pl.col("close") <= 0),
        (
            "volume must be greater than or equal to 0 when present",
            pl.col("volume").is_not_null() & (pl.col("volume") < 0),
        ),
    )

    for label, expression in comparisons:
        count = _violation_count(frame, expression)
        if count > 0:
            issues.append(f"{label}: {count} row(s)")

    return QualityReport(
        passed=not issues,
        row_count=row_count,
        min_ts=min_ts,
        max_ts=max_ts,
        duplicate_count=duplicate_count,
        issues=issues,
    )


def validate_futures_metadata(frame: pl.DataFrame) -> MetadataQualityReport:
    """Run futures metadata quality checks and return a structured report."""

    issues: list[str] = []
    row_count = frame.height

    if row_count == 0:
        issues.append("Metadata DataFrame is empty")

    missing_columns = [column for column in FUTURES_METADATA_COLUMNS if column not in frame.columns]
    if missing_columns:
        issues.append(f"Missing required metadata columns: {', '.join(missing_columns)}")
        return MetadataQualityReport(
            passed=False,
            row_count=row_count,
            duplicate_count=0,
            issues=issues,
        )

    if _null_count(frame, "secid") > 0:
        issues.append("Column secid contains null values")
    if _null_count(frame, "snapshot_ts") > 0:
        issues.append("Column snapshot_ts contains null values")

    duplicate_count = (
        row_count - frame.unique(subset=list(FUTURES_METADATA_UNIQUE_KEY_COLUMNS)).height
    )
    if duplicate_count > 0:
        issues.append(f"Duplicate futures metadata rows by secid + board: {duplicate_count}")

    expected_values = {
        "source": DEFAULT_SOURCE,
        "exchange": DEFAULT_EXCHANGE,
        "engine": DEFAULT_FUTURES_ENGINE,
        "market": DEFAULT_FUTURES_MARKET,
    }
    for column, expected_value in expected_values.items():
        bad_count = _violation_count(frame, pl.col(column) != expected_value)
        if bad_count > 0:
            issues.append(f"Column {column} must equal {expected_value!r}: {bad_count} row(s)")

    return MetadataQualityReport(
        passed=not issues,
        row_count=row_count,
        duplicate_count=duplicate_count,
        issues=issues,
    )
