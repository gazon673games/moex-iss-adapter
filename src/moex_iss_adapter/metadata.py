"""Futures metadata normalization, loading, and search."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from moex_iss_adapter.constants import (
    DEFAULT_EXCHANGE,
    DEFAULT_FUTURES_ENGINE,
    DEFAULT_FUTURES_MARKET,
    DEFAULT_SOURCE,
    FUTURES_METADATA_COLUMNS,
)
from moex_iss_adapter.exceptions import MoexResponseFormatError
from moex_iss_adapter.normalizers import parse_moex_table


def current_snapshot_ts() -> datetime:
    """Return a second-precision UTC timestamp without timezone info."""

    return datetime.now(UTC).replace(microsecond=0, tzinfo=None)


def format_snapshot_ts(snapshot_ts: datetime) -> str:
    """Format a snapshot timestamp for partition/file names."""

    return snapshot_ts.strftime("%Y%m%dT%H%M%SZ")


def empty_futures_metadata_frame() -> pl.DataFrame:
    """Return an empty normalized futures metadata DataFrame."""

    return pl.DataFrame(
        schema={
            "source": pl.Utf8,
            "exchange": pl.Utf8,
            "engine": pl.Utf8,
            "market": pl.Utf8,
            "board": pl.Utf8,
            "secid": pl.Utf8,
            "shortname": pl.Utf8,
            "secname": pl.Utf8,
            "assetcode": pl.Utf8,
            "instrument_type": pl.Utf8,
            "last_trade_date": pl.Date,
            "expiration_date": pl.Date,
            "currency": pl.Utf8,
            "lot_size": pl.Float64,
            "raw_metadata": pl.Utf8,
            "snapshot_ts": pl.Datetime,
        }
    ).select(FUTURES_METADATA_COLUMNS)


def _optional_str(row: Mapping[str, Any], *names: str) -> str | None:
    for name in names:
        value = row.get(name)
        if value is not None:
            text = str(value).strip()
            if text:
                return text
    return None


def _optional_float(row: Mapping[str, Any], *names: str) -> float | None:
    for name in names:
        value = row.get(name)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
    return None


def normalize_futures_metadata(
    response: Mapping[str, Any],
    *,
    snapshot_ts: datetime | None = None,
    engine: str = DEFAULT_FUTURES_ENGINE,
    market: str = DEFAULT_FUTURES_MARKET,
) -> pl.DataFrame:
    """Normalize a MOEX futures securities response to a stable metadata schema."""

    rows = parse_moex_table(response, "securities")
    effective_snapshot_ts = snapshot_ts or current_snapshot_ts()
    if not rows:
        return empty_futures_metadata_frame()

    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        secid = _optional_str(row, "secid")
        if not secid:
            msg = "MOEX futures metadata row is missing SECID"
            raise MoexResponseFormatError(msg)
        normalized_rows.append(
            {
                "source": DEFAULT_SOURCE,
                "exchange": DEFAULT_EXCHANGE,
                "engine": engine,
                "market": market,
                "board": _optional_str(row, "boardid", "board"),
                "secid": secid,
                "shortname": _optional_str(row, "shortname"),
                "secname": _optional_str(row, "secname"),
                "assetcode": _optional_str(row, "assetcode"),
                "instrument_type": _optional_str(row, "sectype", "instrument_type"),
                "last_trade_date": _optional_str(row, "lasttradedate", "last_trade_date"),
                "expiration_date": _optional_str(row, "lastdeldate", "expiration_date"),
                "currency": _optional_str(
                    row,
                    "currency",
                    "currencyid",
                    "settlecurrency",
                    "settle_currency",
                ),
                "lot_size": _optional_float(row, "lotvolume", "lot_size", "lotsize"),
                "raw_metadata": json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                ),
                "snapshot_ts": effective_snapshot_ts,
            }
        )

    return (
        pl.DataFrame(normalized_rows)
        .with_columns(
            pl.col("source").cast(pl.Utf8),
            pl.col("exchange").cast(pl.Utf8),
            pl.col("engine").cast(pl.Utf8),
            pl.col("market").cast(pl.Utf8),
            pl.col("board").cast(pl.Utf8),
            pl.col("secid").cast(pl.Utf8),
            pl.col("shortname").cast(pl.Utf8),
            pl.col("secname").cast(pl.Utf8),
            pl.col("assetcode").cast(pl.Utf8),
            pl.col("instrument_type").cast(pl.Utf8),
            pl.col("last_trade_date").cast(pl.Utf8).str.strptime(pl.Date, strict=False),
            pl.col("expiration_date").cast(pl.Utf8).str.strptime(pl.Date, strict=False),
            pl.col("currency").cast(pl.Utf8),
            pl.col("lot_size").cast(pl.Float64),
            pl.col("raw_metadata").cast(pl.Utf8),
            pl.col("snapshot_ts").cast(pl.Datetime),
        )
        .select(FUTURES_METADATA_COLUMNS)
        .sort(["secid", "board"], nulls_last=True)
    )


def load_futures_metadata_snapshot(path: Path | str) -> pl.DataFrame:
    """Load a normalized futures metadata Parquet snapshot."""

    return pl.read_parquet(Path(path)).select(FUTURES_METADATA_COLUMNS)


def search_futures_metadata(
    frame: pl.DataFrame,
    *,
    query: str | None = None,
    secid: str | None = None,
    shortname: str | None = None,
    secname: str | None = None,
    assetcode: str | None = None,
) -> pl.DataFrame:
    """Search normalized futures metadata by common discovery fields."""

    result = frame
    if query:
        query_text = query.casefold()
        result = result.filter(
            pl.any_horizontal(
                [
                    pl.col(column)
                    .cast(pl.Utf8, strict=False)
                    .str.to_lowercase()
                    .str.contains(query_text, literal=True)
                    .fill_null(False)
                    for column in ("secid", "shortname", "secname", "assetcode")
                ]
            )
        )

    filters = (
        ("secid", secid),
        ("shortname", shortname),
        ("secname", secname),
        ("assetcode", assetcode),
    )
    for column, value in filters:
        if value:
            result = result.filter(
                pl.col(column)
                .cast(pl.Utf8, strict=False)
                .str.to_lowercase()
                .str.contains(value.casefold(), literal=True)
                .fill_null(False)
            )

    return result.select(FUTURES_METADATA_COLUMNS)
