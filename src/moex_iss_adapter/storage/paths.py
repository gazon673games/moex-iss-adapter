"""Storage path builders for MOEX ISS adapter artifacts."""

from __future__ import annotations

from pathlib import Path

from moex_iss_adapter.constants import DEFAULT_EXCHANGE, DEFAULT_SOURCE
from moex_iss_adapter.metadata import format_snapshot_ts


def partition_path(root: Path, *parts: tuple[str, str]) -> Path:
    path = root
    for key, value in parts:
        path = path / f"{key}={value}"
    return path


def partition_value(path: Path, key: str) -> str | None:
    prefix = f"{key}="
    for part in path.parts:
        if part.startswith(prefix):
            value = part[len(prefix) :]
            return value or None
    return None


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
    directory = partition_path(
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
    directory = partition_path(
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
        partition_path(
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
        partition_path(
            root / "normalized" / "metadata",
            ("exchange", DEFAULT_EXCHANGE),
            ("engine", engine),
            ("market", market),
        )
        / "securities"
        / f"snapshot_ts={format_snapshot_ts(snapshot_ts)}"
    )
    return directory / filename
