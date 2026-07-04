"""Futures metadata snapshot storage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import polars as pl

from moex_iss_adapter.constants import DEFAULT_SOURCE
from moex_iss_adapter.metadata import format_snapshot_ts
from moex_iss_adapter.models import MetadataSnapshotInfo
from moex_iss_adapter.storage.io import ensure_writable, write_json_payload, write_parquet_frame
from moex_iss_adapter.storage.paths import (
    build_normalized_futures_metadata_path,
    build_raw_futures_metadata_path,
    partition_value,
)


def _parquet_row_count(path: Path) -> int | None:
    try:
        return pl.scan_parquet(path).select(pl.len().alias("row_count")).collect().item()
    except Exception:
        return None


def list_metadata_snapshots(
    *,
    data_root: Path | str,
    engine: str | None = None,
    market: str | None = None,
    include_row_count: bool = True,
) -> list[MetadataSnapshotInfo]:
    """List saved normalized metadata snapshot Parquet files."""

    metadata_root = Path(data_root) / "normalized" / "metadata"
    if not metadata_root.exists():
        return []

    snapshots: list[MetadataSnapshotInfo] = []
    for path in sorted(metadata_root.rglob("part-000.parquet")):
        if "securities" not in path.parts:
            continue
        exchange_value = partition_value(path, "exchange")
        engine_value = partition_value(path, "engine")
        market_value = partition_value(path, "market")
        snapshot_ts_value = partition_value(path, "snapshot_ts")
        if not all((exchange_value, engine_value, market_value, snapshot_ts_value)):
            continue
        if engine and engine_value != engine:
            continue
        if market and market_value != market:
            continue
        snapshots.append(
            MetadataSnapshotInfo(
                exchange=exchange_value,
                engine=engine_value,
                market=market_value,
                snapshot_ts=snapshot_ts_value,
                parquet_path=path,
                row_count=_parquet_row_count(path) if include_row_count else None,
            )
        )
    return snapshots


def save_raw_futures_metadata(
    *,
    response: dict[str, Any],
    data_root: Path | str,
    engine: str,
    market: str,
    snapshot_ts,
    overwrite: bool = False,
) -> Path:
    path = build_raw_futures_metadata_path(
        data_root=data_root,
        engine=engine,
        market=market,
        snapshot_ts=snapshot_ts,
    )
    ensure_writable(path, overwrite)
    payload = {
        "metadata": {
            "source": DEFAULT_SOURCE,
            "engine": engine,
            "market": market,
            "snapshot_ts": format_snapshot_ts(snapshot_ts),
        },
        "response": response,
    }
    write_json_payload(
        path,
        payload,
        error_message=f"Failed to save raw MOEX futures metadata to {path}",
    )
    return path


def save_normalized_futures_metadata(
    *,
    frame: pl.DataFrame,
    data_root: Path | str,
    engine: str,
    market: str,
    snapshot_ts,
    overwrite: bool = False,
) -> Path:
    path = build_normalized_futures_metadata_path(
        data_root=data_root,
        engine=engine,
        market=market,
        snapshot_ts=snapshot_ts,
    )
    ensure_writable(path, overwrite)
    write_parquet_frame(
        path,
        frame,
        error_message=f"Failed to save normalized MOEX futures metadata to {path}",
    )
    return path
