"""Raw JSON and normalized Parquet storage for MOEX ISS candles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl

from moex_iss_adapter.constants import DEFAULT_EXCHANGE, DEFAULT_SOURCE
from moex_iss_adapter.exceptions import MoexStorageError
from moex_iss_adapter.metadata import format_snapshot_ts
from moex_iss_adapter.models import MetadataSnapshotInfo


def _partition_path(root: Path, *parts: tuple[str, str]) -> Path:
    path = root
    for key, value in parts:
        path = path / f"{key}={value}"
    return path


def build_raw_candles_path(
    *,
    data_root: Path | str,
    engine: str,
    market: str,
    board: str,
    symbol: str,
    timeframe: str,
    from_date: str,
    till_date: str,
) -> Path:
    root = Path(data_root)
    directory = _partition_path(
        root / "raw" / DEFAULT_SOURCE / "candles",
        ("engine", engine),
        ("market", market),
        ("board", board),
        ("symbol", symbol),
        ("timeframe", timeframe),
    )
    return directory / f"from={from_date}_till={till_date}.json"


def build_normalized_candles_path(
    *,
    data_root: Path | str,
    engine: str,
    market: str,
    board: str,
    symbol: str,
    timeframe: str,
    filename: str = "part-000.parquet",
) -> Path:
    root = Path(data_root)
    directory = _partition_path(
        root / "normalized" / "candles",
        ("exchange", DEFAULT_EXCHANGE),
        ("engine", engine),
        ("market", market),
        ("board", board),
        ("symbol", symbol),
        ("timeframe", timeframe),
    )
    return directory / filename


def build_raw_futures_metadata_path(
    *,
    data_root: Path | str,
    engine: str,
    market: str,
    snapshot_ts,
) -> Path:
    root = Path(data_root)
    directory = (
        _partition_path(
            root / "raw" / DEFAULT_SOURCE / "metadata",
            ("engine", engine),
            ("market", market),
        )
        / "securities"
    )
    return directory / f"snapshot_ts={format_snapshot_ts(snapshot_ts)}.json"


def build_normalized_futures_metadata_path(
    *,
    data_root: Path | str,
    engine: str,
    market: str,
    snapshot_ts,
    filename: str = "part-000.parquet",
) -> Path:
    root = Path(data_root)
    directory = (
        _partition_path(
            root / "normalized" / "metadata",
            ("exchange", DEFAULT_EXCHANGE),
            ("engine", engine),
            ("market", market),
        )
        / "securities"
        / f"snapshot_ts={format_snapshot_ts(snapshot_ts)}"
    )
    return directory / filename


def _ensure_writable(path: Path, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        msg = f"Refusing to overwrite existing file without overwrite=True: {path}"
        raise MoexStorageError(msg)
    path.parent.mkdir(parents=True, exist_ok=True)


def _partition_value(path: Path, key: str) -> str | None:
    prefix = f"{key}="
    for part in path.parts:
        if part.startswith(prefix):
            value = part[len(prefix) :]
            return value or None
    return None


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
        exchange_value = _partition_value(path, "exchange")
        engine_value = _partition_value(path, "engine")
        market_value = _partition_value(path, "market")
        snapshot_ts_value = _partition_value(path, "snapshot_ts")
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
    _ensure_writable(path, overwrite)
    payload = {
        "metadata": {
            "source": DEFAULT_SOURCE,
            "engine": engine,
            "market": market,
            "board": board,
            "symbol": symbol,
            "timeframe": timeframe,
            "from_date": from_date,
            "till_date": till_date,
        },
        "pages": responses,
    }
    try:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        msg = f"Failed to save raw MOEX responses to {path}"
        raise MoexStorageError(msg) from exc
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
    _ensure_writable(path, overwrite)
    try:
        frame.write_parquet(path)
    except Exception as exc:  # pragma: no cover - backend exception types vary by version.
        msg = f"Failed to save normalized candles to {path}"
        raise MoexStorageError(msg) from exc
    return path


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
    _ensure_writable(path, overwrite)
    payload = {
        "metadata": {
            "source": DEFAULT_SOURCE,
            "engine": engine,
            "market": market,
            "snapshot_ts": format_snapshot_ts(snapshot_ts),
        },
        "response": response,
    }
    try:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        msg = f"Failed to save raw MOEX futures metadata to {path}"
        raise MoexStorageError(msg) from exc
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
    _ensure_writable(path, overwrite)
    try:
        frame.write_parquet(path)
    except Exception as exc:  # pragma: no cover - backend exception types vary by version.
        msg = f"Failed to save normalized MOEX futures metadata to {path}"
        raise MoexStorageError(msg) from exc
    return path
