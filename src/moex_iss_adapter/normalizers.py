"""Normalize MOEX ISS table responses to canonical OHLCV data."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import polars as pl

from moex_iss_adapter.constants import (
    CANONICAL_OHLCV_COLUMNS,
    DEFAULT_EXCHANGE,
    DEFAULT_SOURCE,
)
from moex_iss_adapter.exceptions import MoexNormalizationError, MoexResponseFormatError

RAW_REQUIRED_CANDLE_COLUMNS = {"begin", "open", "high", "low", "close"}


def empty_canonical_candles_frame() -> pl.DataFrame:
    """Return an empty DataFrame with the canonical schema and stable dtypes."""

    return pl.DataFrame(
        schema={
            "source": pl.Utf8,
            "exchange": pl.Utf8,
            "engine": pl.Utf8,
            "market": pl.Utf8,
            "board": pl.Utf8,
            "symbol": pl.Utf8,
            "timeframe": pl.Utf8,
            "ts": pl.Datetime,
            "open": pl.Float64,
            "high": pl.Float64,
            "low": pl.Float64,
            "close": pl.Float64,
            "volume": pl.Float64,
            "value": pl.Float64,
            "currency": pl.Utf8,
        }
    ).select(CANONICAL_OHLCV_COLUMNS)


def _get_table(response: Mapping[str, Any], table_name: str) -> Mapping[str, Any]:
    table = response.get(table_name)
    if not isinstance(table, Mapping):
        msg = f"MOEX ISS response is missing table {table_name!r}"
        raise MoexResponseFormatError(msg)
    return table


def parse_moex_table(
    response: Mapping[str, Any], table_name: str, *, normalize_column_names: bool = True
) -> list[dict[str, Any]]:
    """Parse a MOEX table object with `columns` and `data` by column name."""

    table = _get_table(response, table_name)
    columns = table.get("columns")
    data = table.get("data")

    if not isinstance(columns, list) or not all(isinstance(column, str) for column in columns):
        msg = f"MOEX ISS table {table_name!r} must contain a string columns list"
        raise MoexResponseFormatError(msg)
    if not isinstance(data, list):
        msg = f"MOEX ISS table {table_name!r} must contain a data list"
        raise MoexResponseFormatError(msg)

    normalized_columns = (
        [column.lower() for column in columns] if normalize_column_names else columns
    )
    if len(set(normalized_columns)) != len(columns):
        raise MoexResponseFormatError(f"MOEX ISS table {table_name!r} contains duplicate columns")
    rows: list[dict[str, Any]] = []
    for row_number, row in enumerate(data):
        if not isinstance(row, list):
            msg = f"MOEX ISS table {table_name!r} row {row_number} must be a list"
            raise MoexResponseFormatError(msg)
        if len(row) != len(columns):
            msg = (
                f"MOEX ISS table {table_name!r} row {row_number} has {len(row)} values "
                f"for {len(columns)} columns"
            )
            raise MoexResponseFormatError(msg)
        rows.append(dict(zip(normalized_columns, row, strict=True)))
    return rows


def count_candle_rows(response: Mapping[str, Any]) -> int:
    """Return the number of candle rows in one MOEX response page."""

    return len(parse_moex_table(response, "candles"))


def normalize_candles(
    responses: Iterable[Mapping[str, Any]],
    *,
    engine: str,
    market: str,
    board: str,
    symbol: str,
    timeframe: str,
) -> pl.DataFrame:
    """Convert one or more MOEX candle pages into canonical OHLCV candles."""

    rows: list[dict[str, Any]] = []
    for response in responses:
        rows.extend(parse_moex_table(response, "candles"))

    if not rows:
        return empty_canonical_candles_frame()

    available_columns = set(rows[0])
    missing_columns = sorted(RAW_REQUIRED_CANDLE_COLUMNS - available_columns)
    if missing_columns:
        msg = f"MOEX candles table missing required columns: {', '.join(missing_columns)}"
        raise MoexResponseFormatError(msg)

    try:
        frame = pl.DataFrame(rows)
        currency_expr = (
            pl.col("currency").cast(pl.Utf8, strict=False)
            if "currency" in frame.columns
            else pl.lit(None, dtype=pl.Utf8)
        )
        if "currencyid" in frame.columns:
            currency_expr = pl.coalesce(
                [currency_expr, pl.col("currencyid").cast(pl.Utf8, strict=False)]
            )

        normalized = (
            frame.with_columns(
                pl.lit(DEFAULT_SOURCE).alias("source"),
                pl.lit(DEFAULT_EXCHANGE).alias("exchange"),
                pl.lit(engine).alias("engine"),
                pl.lit(market).alias("market"),
                pl.lit(board).alias("board"),
                pl.lit(symbol).alias("symbol"),
                pl.lit(timeframe).alias("timeframe"),
                pl.col("begin")
                .cast(pl.Utf8, strict=False)
                .str.strptime(pl.Datetime, strict=False)
                .alias("ts"),
                pl.col("open").cast(pl.Float64, strict=False),
                pl.col("high").cast(pl.Float64, strict=False),
                pl.col("low").cast(pl.Float64, strict=False),
                pl.col("close").cast(pl.Float64, strict=False),
                (
                    pl.col("volume").cast(pl.Float64, strict=False)
                    if "volume" in frame.columns
                    else pl.lit(None, dtype=pl.Float64).alias("volume")
                ),
                (
                    pl.col("value").cast(pl.Float64, strict=False)
                    if "value" in frame.columns
                    else pl.lit(None, dtype=pl.Float64).alias("value")
                ),
                currency_expr.alias("currency"),
            )
            .select(CANONICAL_OHLCV_COLUMNS)
            .unique(maintain_order=True)
            .sort("ts")
        )
    except pl.PolarsError as exc:
        msg = "Failed to normalize MOEX candle response"
        raise MoexNormalizationError(msg) from exc

    if timeframe == "5m":
        return _aggregate_to_5m(normalized)
    return normalized


def _aggregate_to_5m(frame: pl.DataFrame) -> pl.DataFrame:
    if frame.is_empty():
        return frame

    try:
        return (
            frame.with_columns(pl.col("ts").dt.truncate("5m").alias("ts"))
            .group_by(
                [
                    "source",
                    "exchange",
                    "engine",
                    "market",
                    "board",
                    "symbol",
                    "timeframe",
                    "ts",
                ],
                maintain_order=True,
            )
            .agg(
                pl.col("open").first(),
                pl.col("high").max(),
                pl.col("low").min(),
                pl.col("close").last(),
                pl.col("volume").sum(),
                pl.col("value").sum(),
                pl.col("currency").drop_nulls().first(),
            )
            .select(CANONICAL_OHLCV_COLUMNS)
            .sort("ts")
        )
    except pl.PolarsError as exc:
        msg = "Failed to aggregate MOEX candle response to 5m timeframe"
        raise MoexNormalizationError(msg) from exc
