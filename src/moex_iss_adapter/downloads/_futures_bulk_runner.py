"""Bulk futures metadata selection and candle preparation workflows."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from moex_iss_adapter.client import MoexIssClient
from moex_iss_adapter.constants import (
    DEFAULT_TIMEFRAME,
)
from moex_iss_adapter.downloads._futures_bulk_download import (
    _download_one_bulk_contract,
    _manual_include_contracts,
    _merge_contracts,
)
from moex_iss_adapter.downloads._futures_bulk_filters import (
    derive_contract_date_range,
)
from moex_iss_adapter.downloads._futures_bulk_metadata import (
    _fetch_metadata_snapshot,
    _load_metadata_snapshot,
    select_futures_chain_contracts,
)
from moex_iss_adapter.downloads.futures_history import (
    search_historical_futures_contracts,
)
from moex_iss_adapter.exceptions import MoexIssAdapterError
from moex_iss_adapter.metadata import (
    format_snapshot_ts,
)
from moex_iss_adapter.models import (
    FuturesBulkResult,
    FuturesBulkSkip,
    MoexIssConfig,
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
