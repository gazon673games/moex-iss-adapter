"""Bulk futures metadata selection and candle preparation workflows."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime
from pathlib import Path
from typing import Any

import polars as pl

from moex_iss_adapter.client import MoexIssClient
from moex_iss_adapter.constants import (
    DEFAULT_FUTURES_BOARD,
    DEFAULT_FUTURES_ENGINE,
    DEFAULT_FUTURES_MARKET,
    DEFAULT_TIMEFRAME,
)
from moex_iss_adapter.downloads.candles import (
    CandleDownloadRequest,
    download_candle_pages,
)
from moex_iss_adapter.downloads.futures import fetch_futures_securities_response
from moex_iss_adapter.downloads.futures_history import (
    fetch_futures_contract_details,
    search_historical_futures_contracts,
)
from moex_iss_adapter.exceptions import MoexIssAdapterError
from moex_iss_adapter.metadata import (
    current_snapshot_ts,
    format_snapshot_ts,
    load_futures_metadata_snapshot,
    normalize_futures_metadata,
)
from moex_iss_adapter.models import (
    DownloadResult,
    FuturesBulkResult,
    FuturesBulkSkip,
    FuturesChainContract,
    FuturesChainSelection,
    FuturesContractDateRange,
    MetadataSnapshotResult,
    MoexIssConfig,
)
from moex_iss_adapter.normalizers import normalize_candles
from moex_iss_adapter.quality import validate_candles, validate_futures_metadata
from moex_iss_adapter.storage import (
    save_normalized_candles,
    save_normalized_futures_metadata,
    save_raw_candles,
    save_raw_futures_metadata,
)
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


def _parse_user_date(value: str, option_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        msg = f"{option_name} must be an ISO date in YYYY-MM-DD format"
        raise MoexIssAdapterError(msg) from exc


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
        return FuturesBulkSkip(board=board, reason="missing_secid", metadata_found=False)
    if not board:
        return FuturesBulkSkip(secid=secid, reason="missing_board", metadata_found=True)
    return FuturesChainContract(
        secid=secid,
        board=board,
        shortname=_optional_str(row.get("shortname")),
        secname=_optional_str(row.get("secname")),
        assetcode=_optional_str(row.get("assetcode")),
        last_trade_date=_optional_date(row.get("last_trade_date")),
        expiration_date=_optional_date(row.get("expiration_date")),
        metadata_found=True,
        source_endpoint="normalized_metadata_snapshot",
    )


def _contract_sort_key(contract: FuturesChainContract) -> tuple[bool, date, str]:
    sort_date = contract.expiration_date or contract.last_trade_date
    return sort_date is None, sort_date or date.max, contract.secid


def derive_contract_date_range(
    contract: FuturesChainContract,
    *,
    user_from_date: str,
    user_till_date: str,
    use_contract_date_ranges: bool,
) -> FuturesContractDateRange | FuturesBulkSkip:
    """Derive the MOEX candle request range for one selected futures contract."""

    from_date = _parse_user_date(user_from_date, "--from-date")
    _parse_user_date(user_till_date, "--till-date")
    if not use_contract_date_ranges:
        return FuturesContractDateRange(
            secid=contract.secid,
            board=contract.board,
            from_date=user_from_date,
            till_date=user_till_date,
        )

    metadata_end_date = contract.expiration_date or contract.last_trade_date
    if metadata_end_date is not None and metadata_end_date < from_date:
        return FuturesBulkSkip(
            secid=contract.secid,
            board=contract.board,
            reason="expired_before_from_date",
            metadata_found=contract.metadata_found,
        )

    till_date = metadata_end_date.isoformat() if metadata_end_date else user_till_date
    return FuturesContractDateRange(
        secid=contract.secid,
        board=contract.board,
        from_date=user_from_date,
        till_date=till_date,
    )


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


def _merge_contracts(
    contracts: list[FuturesChainContract],
    additions: Iterable[FuturesChainContract],
) -> list[FuturesChainContract]:
    result = list(contracts)
    seen = {_contract_key(contract.secid) for contract in result}
    for contract in additions:
        key = _contract_key(contract.secid)
        if key in seen:
            continue
        seen.add(key)
        result.append(contract)
    result.sort(key=_contract_sort_key)
    return result


def _manual_include_contracts(
    *,
    include_secids: Iterable[str] | None,
    selected_contracts: Iterable[FuturesChainContract],
    exclude_secids: Iterable[str] | None,
    board: str | None,
    config: MoexIssConfig,
    client: MoexIssClient,
) -> list[FuturesChainContract]:
    selected = {_contract_key(contract.secid) for contract in selected_contracts}
    excluded = _casefold_set(exclude_secids)
    additions: list[FuturesChainContract] = []
    for raw_secid in include_secids or ():
        secid = raw_secid.strip()
        if not secid:
            continue
        key = _contract_key(secid)
        if key in selected or key in excluded:
            continue
        try:
            details = fetch_futures_contract_details(
                secid=secid,
                config=config,
                client=client,
            )
        except MoexIssAdapterError:
            details = None

        if details is not None:
            if board and details.board.casefold() != board.casefold():
                continue
            additions.append(details)
            continue

        additions.append(
            FuturesChainContract(
                secid=secid,
                board=board or DEFAULT_FUTURES_BOARD,
                metadata_found=False,
                source_endpoint="manual_include",
            )
        )
    return additions


def _download_one_bulk_contract(
    *,
    client: MoexIssClient,
    config: MoexIssConfig,
    date_range: FuturesContractDateRange,
    timeframe: str,
    save_raw: bool,
    save_normalized: bool,
    data_root: Path | str,
    overwrite: bool,
) -> DownloadResult:
    request = CandleDownloadRequest(
        symbol=date_range.secid,
        engine=DEFAULT_FUTURES_ENGINE,
        market=DEFAULT_FUTURES_MARKET,
        board=date_range.board,
        request_board=date_range.board,
        timeframe=timeframe,
        from_date=date_range.from_date,
        till_date=date_range.till_date,
        save_raw=save_raw,
        save_normalized=False,
        data_root=data_root,
        overwrite=overwrite,
    )
    raw_pages = download_candle_pages(client=client, config=config, request=request)
    normalized = normalize_candles(
        raw_pages,
        engine=request.engine,
        market=request.market,
        board=request.board,
        symbol=request.symbol,
        timeframe=request.timeframe,
    )
    quality_report = validate_candles(normalized)

    raw_path = None
    normalized_path = None
    if save_raw:
        raw_path = save_raw_candles(
            responses=raw_pages,
            data_root=data_root,
            engine=request.engine,
            market=request.market,
            board=request.board,
            symbol=request.symbol,
            timeframe=request.timeframe,
            from_date=request.from_date,
            till_date=request.till_date,
            overwrite=overwrite,
        )
    if save_normalized and quality_report.row_count > 0:
        normalized_path = save_normalized_candles(
            frame=normalized,
            data_root=data_root,
            engine=request.engine,
            market=request.market,
            board=request.board,
            symbol=request.symbol,
            timeframe=request.timeframe,
            overwrite=overwrite,
        )

    return DownloadResult(
        symbol=request.symbol,
        engine=request.engine,
        market=request.market,
        board=request.board,
        timeframe=request.timeframe,
        from_date=request.from_date,
        till_date=request.till_date,
        row_count=quality_report.row_count,
        min_ts=quality_report.min_ts,
        max_ts=quality_report.max_ts,
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
    use_contract_date_ranges: bool = False,
    include_expired: bool = False,
    min_successful_contracts: int = 1,
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
        selected_contracts = list(selection.contracts)

        historical_query = query or asset_code or secid_prefix
        if include_expired and historical_query:
            historical_contracts = search_historical_futures_contracts(
                query=historical_query,
                secid_prefix=secid_prefix,
                asset_code=asset_code,
                exclude_secids=exclude_secids,
                client=effective_client,
                config=effective_config,
            )
            if board:
                historical_contracts = [
                    contract
                    for contract in historical_contracts
                    if contract.board.casefold() == board.casefold()
                ]
            selected_contracts = _merge_contracts(selected_contracts, historical_contracts)

        manual_contracts = _manual_include_contracts(
            include_secids=include_secids,
            selected_contracts=selected_contracts,
            exclude_secids=exclude_secids,
            board=board,
            config=effective_config,
            client=effective_client,
        )
        selected_contracts = _merge_contracts(selected_contracts, manual_contracts)

        downloads = []
        for contract in selected_contracts:
            date_range = derive_contract_date_range(
                contract,
                user_from_date=from_date,
                user_till_date=till_date,
                use_contract_date_ranges=use_contract_date_ranges,
            )
            if isinstance(date_range, FuturesBulkSkip):
                skipped.append(date_range)
                continue

            try:
                result = _download_one_bulk_contract(
                    client=effective_client,
                    config=effective_config,
                    date_range=date_range,
                    timeframe=timeframe,
                    save_raw=save_raw,
                    save_normalized=save_normalized,
                    data_root=data_root,
                    overwrite=overwrite,
                )
            except MoexIssAdapterError as exc:
                skipped.append(
                    FuturesBulkSkip(
                        secid=contract.secid,
                        board=contract.board,
                        reason=f"download_failed: {exc}",
                        metadata_found=contract.metadata_found,
                        candles_found=False,
                    )
                )
                continue

            if result.row_count == 0:
                skipped.append(
                    FuturesBulkSkip(
                        secid=contract.secid,
                        board=contract.board,
                        reason="no_rows",
                        metadata_found=contract.metadata_found,
                        candles_found=False,
                        row_count=0,
                    )
                )
                continue
            downloads.append(result)

        return FuturesBulkResult(
            metadata_snapshot=metadata_snapshot,
            contracts_found=max(selection.contracts_found, len(selected_contracts)),
            min_successful_contracts=min_successful_contracts,
            selected_contracts=selected_contracts,
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
        "successful_contracts": result.successful_contracts,
        "failed_contracts": result.failed_contracts,
        "rows_total": result.rows_total,
        "downloaded_contracts": result.download_results,
        "skipped_contracts": result.skipped_contracts,
    }
