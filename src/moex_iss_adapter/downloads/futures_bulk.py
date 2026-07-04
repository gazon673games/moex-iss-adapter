"""Bulk futures metadata selection and candle preparation workflows."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any

import polars as pl

from moex_iss_adapter.client import MoexIssClient
from moex_iss_adapter.constants import (
    DEFAULT_FUTURES_ENGINE,
    DEFAULT_FUTURES_MARKET,
    DEFAULT_TIMEFRAME,
)
from moex_iss_adapter.downloads.futures import (
    download_futures_candles,
    fetch_futures_securities_response,
)
from moex_iss_adapter.exceptions import MoexIssAdapterError
from moex_iss_adapter.metadata import (
    current_snapshot_ts,
    format_snapshot_ts,
    load_futures_metadata_snapshot,
    normalize_futures_metadata,
)
from moex_iss_adapter.models import (
    FuturesBulkResult,
    FuturesBulkSkip,
    FuturesChainContract,
    FuturesChainSelection,
    MetadataSnapshotResult,
    MoexIssConfig,
)
from moex_iss_adapter.quality import validate_futures_metadata
from moex_iss_adapter.storage import save_normalized_futures_metadata, save_raw_futures_metadata
from moex_iss_adapter.storage.paths import partition_value

FUTURES_BULK_QUERY_FIELDS = ("secid", "shortname", "secname", "assetcode")


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _contains(value: Any, needle: str) -> bool:
    return needle.casefold() in str(value or "").casefold()


def _casefold_set(values: Iterable[str] | None) -> set[str]:
    return {value.casefold() for value in values or () if value.strip()}


def _matches_filters(
    row: Mapping[str, Any],
    *,
    query: str | None,
    asset_code: str | None,
    secid_prefix: str | None,
    include_secids: set[str],
    exclude_secids: set[str],
    board: str | None,
) -> bool:
    secid = _optional_str(row.get("secid"))
    if include_secids and (secid is None or secid.casefold() not in include_secids):
        return False
    if exclude_secids and secid is not None and secid.casefold() in exclude_secids:
        return False
    if query and not any(_contains(row.get(field), query) for field in FUTURES_BULK_QUERY_FIELDS):
        return False
    if asset_code and not _contains(row.get("assetcode"), asset_code):
        return False
    if secid_prefix and (secid is None or not secid.casefold().startswith(secid_prefix.casefold())):
        return False
    if board:
        row_board = _optional_str(row.get("board"))
        if row_board is None or row_board.casefold() != board.casefold():
            return False
    return True


def _contract_from_row(row: Mapping[str, Any]) -> FuturesChainContract | FuturesBulkSkip:
    secid = _optional_str(row.get("secid"))
    board = _optional_str(row.get("board"))
    if not secid:
        return FuturesBulkSkip(board=board, reason="missing secid")
    if not board:
        return FuturesBulkSkip(secid=secid, reason="missing board")
    return FuturesChainContract(
        secid=secid,
        board=board,
        shortname=_optional_str(row.get("shortname")),
        secname=_optional_str(row.get("secname")),
        assetcode=_optional_str(row.get("assetcode")),
        last_trade_date=_optional_date(row.get("last_trade_date")),
        expiration_date=_optional_date(row.get("expiration_date")),
    )


def _contract_sort_key(contract: FuturesChainContract) -> tuple[bool, date, str]:
    sort_date = contract.expiration_date or contract.last_trade_date
    return sort_date is None, sort_date or date.max, contract.secid


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
                    reason="not selected by limit",
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


def prepare_futures_chain_data(
    *,
    from_date: str,
    till_date: str,
    query: str | None = None,
    timeframe: str = DEFAULT_TIMEFRAME,
    asset_code: str | None = None,
    secid_prefix: str | None = None,
    include_secids: Iterable[str] | None = None,
    exclude_secids: Iterable[str] | None = None,
    limit: int | None = None,
    board: str | None = None,
    metadata_path: Path | str | None = None,
    save_raw: bool = False,
    save_normalized: bool = False,
    data_root: Path | str = "data",
    overwrite: bool = False,
    config: MoexIssConfig | None = None,
    client: MoexIssClient | None = None,
) -> FuturesBulkResult:
    """Prepare concrete futures candle inputs for downstream chain research."""

    effective_config = config or MoexIssConfig()
    owns_client = client is None
    effective_client = client or MoexIssClient(effective_config)
    try:
        if metadata_path is not None:
            frame, metadata_snapshot = _load_metadata_snapshot(metadata_path)
        else:
            frame, metadata_snapshot = _fetch_metadata_snapshot(
                save_raw=save_raw,
                save_normalized=save_normalized,
                data_root=data_root,
                overwrite=overwrite,
                client=effective_client,
                config=effective_config,
            )

        selection = select_futures_chain_contracts(
            frame,
            query=query,
            asset_code=asset_code,
            secid_prefix=secid_prefix,
            include_secids=include_secids,
            exclude_secids=exclude_secids,
            limit=limit,
            board=board,
        )

        skipped = list(selection.skipped)
        downloads = []
        for contract in selection.contracts:
            try:
                result = download_futures_candles(
                    symbol=contract.secid,
                    board=contract.board,
                    timeframe=timeframe,
                    from_date=from_date,
                    till_date=till_date,
                    save_raw=save_raw,
                    save_normalized=save_normalized,
                    data_root=data_root,
                    overwrite=overwrite,
                    config=effective_config,
                    client=effective_client,
                )
            except MoexIssAdapterError as exc:
                skipped.append(
                    FuturesBulkSkip(
                        secid=contract.secid,
                        board=contract.board,
                        reason=f"download failed: {exc}",
                    )
                )
                continue

            if result.row_count == 0:
                skipped.append(
                    FuturesBulkSkip(
                        secid=contract.secid,
                        board=contract.board,
                        reason="no candle rows",
                    )
                )
                continue
            downloads.append(result)

        return FuturesBulkResult(
            metadata_snapshot=metadata_snapshot,
            contracts_found=selection.contracts_found,
            selected_contracts=selection.contracts,
            download_results=downloads,
            skipped_contracts=skipped,
        )
    finally:
        if owns_client:
            effective_client.close()


def format_futures_bulk_summary(result: FuturesBulkResult) -> dict[str, object]:
    """Return the compact report fields expected by the CLI."""

    return {
        "metadata_snapshot_ts": format_snapshot_ts(result.metadata_snapshot_ts),
        "contracts_found": result.contracts_found,
        "contracts_selected": result.contracts_selected,
        "contracts_downloaded": result.contracts_downloaded,
        "contracts_skipped": result.contracts_skipped,
        "rows_total": result.rows_total,
        "normalized_paths": result.normalized_paths,
        "skipped_reasons": result.skipped_contracts,
    }
