"""Raw and normalized candle storage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl

from moex_iss_adapter.constants import DEFAULT_SOURCE
from moex_iss_adapter.endpoints import moex_interval_for_timeframe
from moex_iss_adapter.storage.io import ensure_writable, write_json_payload, write_parquet_frame
from moex_iss_adapter.storage.paths import build_normalized_candles_path, build_raw_candles_path


def save_raw_candles(
    *,
    responses: list[dict[str, Any]],
    data_root: Path | str,
    engine: str,
    market: str,
    board: str,
    symbol: str,
    timeframe: str,
    from_date: str,
    till_date: str,
    overwrite: bool = False,
) -> Path:
    path = build_raw_candles_path(
        data_root=data_root,
        engine=engine,
        market=market,
        board=board,
        symbol=symbol,
        timeframe=timeframe,
        from_date=from_date,
        till_date=till_date,
    )
    ensure_writable(path, overwrite)
    payload = {
        "metadata": {
            "source": DEFAULT_SOURCE,
            "engine": engine,
            "market": market,
            "board": board,
            "symbol": symbol,
            "timeframe": timeframe,
            "moex_interval": moex_interval_for_timeframe(timeframe),
            "from_date": from_date,
            "till_date": till_date,
        },
        "pages": responses,
    }
    write_json_payload(
        path,
        payload,
        error_message=f"Failed to save raw MOEX responses to {path}",
    )
    return path


def save_normalized_candles(
    *,
    frame: pl.DataFrame,
    data_root: Path | str,
    engine: str,
    market: str,
    board: str,
    symbol: str,
    timeframe: str,
    overwrite: bool = False,
) -> Path:
    path = build_normalized_candles_path(
        data_root=data_root,
        engine=engine,
        market=market,
        board=board,
        symbol=symbol,
        timeframe=timeframe,
    )
    ensure_writable(path, overwrite)
    write_parquet_frame(
        path,
        frame,
        error_message=f"Failed to save normalized candles to {path}",
    )
    return path
