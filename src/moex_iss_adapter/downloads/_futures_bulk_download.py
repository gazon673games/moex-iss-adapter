"""Bulk futures metadata selection and candle preparation workflows."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from moex_iss_adapter.client import MoexIssClient
from moex_iss_adapter.constants import (
    DEFAULT_FUTURES_BOARD,
    DEFAULT_FUTURES_ENGINE,
    DEFAULT_FUTURES_MARKET,
)
from moex_iss_adapter.downloads._futures_bulk_filters import (
    _casefold_set,
    _contract_sort_key,
)
from moex_iss_adapter.downloads._futures_bulk_metadata import (
    _contract_key,
)
from moex_iss_adapter.downloads.candles import (
    CandleDownloadRequest,
    download_candle_pages,
)
from moex_iss_adapter.downloads.futures_history import (
    fetch_futures_contract_details,
)
from moex_iss_adapter.exceptions import MoexIssAdapterError
from moex_iss_adapter.models import (
    DownloadResult,
    FuturesChainContract,
    FuturesContractDateRange,
    MoexIssConfig,
)
from moex_iss_adapter.normalizers import normalize_candles
from moex_iss_adapter.quality import validate_candles
from moex_iss_adapter.storage import (
    save_normalized_candles,
    save_raw_candles,
)


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
