"""Diagnostics for normalized candle datasets."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import polars as pl

from moex_iss_adapter.constants import (
    DEFAULT_FUTURES_BOARD,
    DEFAULT_FUTURES_ENGINE,
    DEFAULT_FUTURES_MARKET,
)


def find_normalized_candle_paths(
    *,
    data_root: Path | str,
    engine: str = DEFAULT_FUTURES_ENGINE,
    market: str = DEFAULT_FUTURES_MARKET,
    board: str = DEFAULT_FUTURES_BOARD,
    timeframe: str,
    symbol_prefix: str | None = None,
) -> list[Path]:
    """Find normalized candle Parquet files by storage partitions."""

    root = (
        Path(data_root)
        / "normalized"
        / "candles"
        / "exchange=MOEX"
        / f"engine={engine}"
        / f"market={market}"
        / f"board={board}"
    )
    paths = []
    for path in root.glob(f"symbol=*/timeframe={timeframe}/part-000.parquet"):
        symbol = path.parents[1].name.removeprefix("symbol=")
        if symbol_prefix and not symbol.upper().startswith(symbol_prefix.upper()):
            continue
        paths.append(path)
    return sorted(paths, key=Path.as_posix)


def intraday_coverage_record(frame: pl.DataFrame, *, symbol: str | None = None) -> dict[str, Any]:
    """Compute lightweight intraday coverage diagnostics for one symbol frame."""

    if frame.is_empty():
        return {
            "symbol": symbol or "",
            "row_count": 0,
            "min_ts": None,
            "max_ts": None,
            "trading_day_count": 0,
            "duplicate_ts_count": 0,
            "null_ohlc_count": 0,
            "max_intraday_gap_minutes": None,
            "large_gap_count": 0,
        }

    sorted_frame = frame.sort("ts")
    resolved_symbol = symbol or str(sorted_frame.get_column("symbol")[0])
    timestamps = sorted_frame.get_column("ts").to_list()
    trading_days = {timestamp.date() for timestamp in timestamps if isinstance(timestamp, datetime)}
    duplicate_count = sorted_frame.height - sorted_frame.unique(subset=["symbol", "ts"]).height
    null_ohlc_count = int(
        sorted_frame.select(
            pl.any_horizontal(
                pl.col("open").is_null(),
                pl.col("high").is_null(),
                pl.col("low").is_null(),
                pl.col("close").is_null(),
            ).sum()
        ).item()
    )
    gaps = [
        (current - previous).total_seconds() / 60
        for previous, current in zip(timestamps, timestamps[1:], strict=False)
        if isinstance(previous, datetime)
        and isinstance(current, datetime)
        and previous.date() == current.date()
    ]

    return {
        "symbol": resolved_symbol,
        "row_count": sorted_frame.height,
        "min_ts": min(timestamps),
        "max_ts": max(timestamps),
        "trading_day_count": len(trading_days),
        "duplicate_ts_count": duplicate_count,
        "null_ohlc_count": null_ohlc_count,
        "max_intraday_gap_minutes": max(gaps) if gaps else None,
        "large_gap_count": sum(1 for gap in gaps if gap > 30),
    }


def intraday_coverage_report(paths: list[Path]) -> dict[str, Any]:
    """Build a JSON-serializable intraday coverage report for normalized Parquet files."""

    records = []
    for path in sorted(paths, key=Path.as_posix):
        frame = pl.read_parquet(path)
        records.append({**intraday_coverage_record(frame), "path": path.as_posix()})

    total_rows = sum(int(record["row_count"]) for record in records)
    min_values = [record["min_ts"] for record in records if record["min_ts"] is not None]
    max_values = [record["max_ts"] for record in records if record["max_ts"] is not None]
    largest = max(records, key=lambda record: int(record["row_count"]), default=None)
    large_gap_symbols = [
        str(record["symbol"]) for record in records if int(record["large_gap_count"]) > 0
    ]

    return {
        "generated_at": datetime.now(UTC),
        "summary": {
            "contracts_reported": len(records),
            "total_rows": total_rows,
            "min_ts": min(min_values) if min_values else None,
            "max_ts": max(max_values) if max_values else None,
            "largest_contract_by_rows": largest["symbol"] if largest else None,
            "contracts_with_large_intraday_gaps": large_gap_symbols,
        },
        "contracts": records,
    }


def write_intraday_coverage_report(
    paths: list[Path],
    *,
    json_path: Path,
    csv_path: Path | None = None,
) -> dict[str, Any]:
    """Write intraday coverage diagnostics as JSON and optionally CSV."""

    report = intraday_coverage_report(paths)
    serializable_report = _json_ready(report)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(serializable_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if csv_path is not None:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        pl.DataFrame(serializable_report["contracts"]).write_csv(csv_path)
    return report


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
