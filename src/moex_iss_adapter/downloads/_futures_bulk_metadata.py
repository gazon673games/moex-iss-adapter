"""Bulk futures metadata selection and candle preparation workflows."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

import polars as pl

from moex_iss_adapter.client import MoexIssClient
from moex_iss_adapter.constants import (
    DEFAULT_FUTURES_ENGINE,
    DEFAULT_FUTURES_MARKET,
)
from moex_iss_adapter.downloads._futures_bulk_filters import (
    _casefold_set,
    _contract_from_row,
    _contract_sort_key,
    _matches_filters,
)
from moex_iss_adapter.downloads.futures import fetch_futures_securities_response
from moex_iss_adapter.metadata import (
    current_snapshot_ts,
    load_futures_metadata_snapshot,
    normalize_futures_metadata,
)
from moex_iss_adapter.models import (
    FuturesBulkSkip,
    FuturesChainContract,
    FuturesChainSelection,
    MetadataSnapshotResult,
    MoexIssConfig,
)
from moex_iss_adapter.quality import validate_futures_metadata
from moex_iss_adapter.storage import (
    save_normalized_futures_metadata,
    save_raw_futures_metadata,
)
from moex_iss_adapter.storage.paths import partition_value


def select_futures_chain_contracts(
    frame: pl.DataFrame,
    *,
    query: str | None = None,
    asset_code: str | None = None,
    secid_prefix: str | None = None,
    include_secids: Iterable[str] | None = None,
    exclude_secids: Iterable[str] | None = None,
    limit: int | None = None,
    board: str | None = None,
) -> FuturesChainSelection:
    """Filter normalized futures metadata into concrete contracts to download."""

    include_set = _casefold_set(include_secids)
    exclude_set = _casefold_set(exclude_secids)
    matched_rows = [
        row
        for row in frame.iter_rows(named=True)
        if _matches_filters(
            row,
            query=query,
            asset_code=asset_code,
            secid_prefix=secid_prefix,
            include_secids=include_set,
            exclude_secids=exclude_set,
            board=board,
        )
    ]

    contracts: list[FuturesChainContract] = []
    skipped: list[FuturesBulkSkip] = []
    for row in matched_rows:
        candidate = _contract_from_row(row)
        if isinstance(candidate, FuturesBulkSkip):
            skipped.append(candidate)
        else:
            contracts.append(candidate)

    contracts.sort(key=_contract_sort_key)
    if limit is not None and len(contracts) > limit:
        for contract in contracts[limit:]:
            skipped.append(
                FuturesBulkSkip(
                    secid=contract.secid,
                    board=contract.board,
                    reason="not_selected_by_limit",
                    metadata_found=contract.metadata_found,
                )
            )
        contracts = contracts[:limit]

    return FuturesChainSelection(
        contracts_found=len(matched_rows),
        contracts=contracts,
        skipped=skipped,
    )


def _snapshot_ts_from_path(path: Path) -> datetime | None:
    value = partition_value(path, "snapshot_ts")
    if value is None and path.parent.name.startswith("snapshot_ts="):
        value = path.parent.name.removeprefix("snapshot_ts=")
    if value is None:
        return None
    try:
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ")
    except ValueError:
        return None


def _snapshot_ts_from_frame(frame: pl.DataFrame, metadata_path: Path | None = None) -> datetime:
    if "snapshot_ts" in frame.columns and not frame.is_empty():
        value = frame.select(pl.col("snapshot_ts").drop_nulls().min()).item()
        if isinstance(value, datetime):
            return value.replace(tzinfo=None)
    if metadata_path is not None:
        path_snapshot_ts = _snapshot_ts_from_path(metadata_path)
        if path_snapshot_ts is not None:
            return path_snapshot_ts
    return current_snapshot_ts()


def _load_metadata_snapshot(
    metadata_path: Path | str,
) -> tuple[pl.DataFrame, MetadataSnapshotResult]:
    path = Path(metadata_path)
    frame = load_futures_metadata_snapshot(path)
    quality_report = validate_futures_metadata(frame)
    snapshot_ts = _snapshot_ts_from_frame(frame, path)
    return frame, MetadataSnapshotResult(
        engine=DEFAULT_FUTURES_ENGINE,
        market=DEFAULT_FUTURES_MARKET,
        row_count=quality_report.row_count,
        snapshot_ts=snapshot_ts,
        raw_path=None,
        normalized_path=path,
        quality_report=quality_report,
    )


def _fetch_metadata_snapshot(
    *,
    save_raw: bool,
    save_normalized: bool,
    data_root: Path | str,
    overwrite: bool,
    client: MoexIssClient,
    config: MoexIssConfig,
) -> tuple[pl.DataFrame, MetadataSnapshotResult]:
    snapshot_ts = current_snapshot_ts()
    raw_response = fetch_futures_securities_response(
        engine=DEFAULT_FUTURES_ENGINE,
        market=DEFAULT_FUTURES_MARKET,
        config=config,
        client=client,
    )
    frame = normalize_futures_metadata(
        raw_response,
        snapshot_ts=snapshot_ts,
        engine=DEFAULT_FUTURES_ENGINE,
        market=DEFAULT_FUTURES_MARKET,
    )
    quality_report = validate_futures_metadata(frame)

    raw_path = None
    normalized_path = None
    if save_raw:
        raw_path = save_raw_futures_metadata(
            response=raw_response,
            data_root=data_root,
            engine=DEFAULT_FUTURES_ENGINE,
            market=DEFAULT_FUTURES_MARKET,
            snapshot_ts=snapshot_ts,
            overwrite=overwrite,
        )
    if save_normalized:
        normalized_path = save_normalized_futures_metadata(
            frame=frame,
            data_root=data_root,
            engine=DEFAULT_FUTURES_ENGINE,
            market=DEFAULT_FUTURES_MARKET,
            snapshot_ts=snapshot_ts,
            overwrite=overwrite,
        )

    return frame, MetadataSnapshotResult(
        engine=DEFAULT_FUTURES_ENGINE,
        market=DEFAULT_FUTURES_MARKET,
        row_count=quality_report.row_count,
        snapshot_ts=snapshot_ts,
        raw_path=raw_path,
        normalized_path=normalized_path,
        quality_report=quality_report,
    )


def _contract_key(secid: str) -> str:
    return secid.casefold()
