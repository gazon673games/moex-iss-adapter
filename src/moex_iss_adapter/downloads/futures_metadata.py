"""Futures metadata snapshot application services."""

from __future__ import annotations

from pathlib import Path

from moex_iss_adapter.client import MoexIssClient
from moex_iss_adapter.constants import DEFAULT_FUTURES_ENGINE, DEFAULT_FUTURES_MARKET
from moex_iss_adapter.downloads.futures import fetch_futures_securities_response
from moex_iss_adapter.metadata import current_snapshot_ts, normalize_futures_metadata
from moex_iss_adapter.models import MetadataSnapshotResult, MoexIssConfig
from moex_iss_adapter.quality import validate_futures_metadata
from moex_iss_adapter.storage import save_normalized_futures_metadata, save_raw_futures_metadata


def save_futures_metadata_snapshot(
    *,
    save_raw: bool = False,
    save_normalized: bool = False,
    data_root: Path | str = "data",
    overwrite: bool = False,
    snapshot_ts=None,
    engine: str = DEFAULT_FUTURES_ENGINE,
    market: str = DEFAULT_FUTURES_MARKET,
    config: MoexIssConfig | None = None,
    client: MoexIssClient | None = None,
) -> MetadataSnapshotResult:
    """Fetch, normalize, validate, and optionally save futures securities metadata."""

    effective_snapshot_ts = snapshot_ts or current_snapshot_ts()
    raw_response = fetch_futures_securities_response(
        engine=engine,
        market=market,
        config=config,
        client=client,
    )
    normalized = normalize_futures_metadata(
        raw_response,
        snapshot_ts=effective_snapshot_ts,
        engine=engine,
        market=market,
    )
    quality_report = validate_futures_metadata(normalized)

    raw_path = None
    normalized_path = None
    if save_raw:
        raw_path = save_raw_futures_metadata(
            response=raw_response,
            data_root=data_root,
            engine=engine,
            market=market,
            snapshot_ts=effective_snapshot_ts,
            overwrite=overwrite,
        )
    if save_normalized:
        normalized_path = save_normalized_futures_metadata(
            frame=normalized,
            data_root=data_root,
            engine=engine,
            market=market,
            snapshot_ts=effective_snapshot_ts,
            overwrite=overwrite,
        )

    return MetadataSnapshotResult(
        engine=engine,
        market=market,
        row_count=quality_report.row_count,
        snapshot_ts=effective_snapshot_ts,
        raw_path=raw_path,
        normalized_path=normalized_path,
        quality_report=quality_report,
    )
