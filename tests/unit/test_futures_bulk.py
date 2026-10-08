from __future__ import annotations

from datetime import date

import polars as pl
from tests.unit.test_futures_bulk_support import SNAPSHOT_TS, FakeBulkFuturesClient

from moex_iss_adapter.downloads.futures_bulk import (
    derive_contract_date_range,
    format_futures_bulk_summary,
    prepare_futures_chain_data,
    select_futures_chain_contracts,
)
from moex_iss_adapter.metadata import normalize_futures_metadata
from moex_iss_adapter.models import (
    FuturesBulkSkip,
    FuturesChainContract,
    FuturesContractDateRange,
    MoexIssConfig,
)


def test_selects_futures_metadata_by_query(futures_securities_response: dict) -> None:
    frame = normalize_futures_metadata(futures_securities_response, snapshot_ts=SNAPSHOT_TS)

    selection = select_futures_chain_contracts(frame, query="cny")

    assert selection.contracts_found > 1
    assert {contract.secid for contract in selection.contracts}.issuperset({"CNYRUBF", "CRU6"})
    assert all(contract.board == "RFUD" for contract in selection.contracts)


def test_include_and_exclude_secid_filters(futures_securities_response: dict) -> None:
    frame = normalize_futures_metadata(futures_securities_response, snapshot_ts=SNAPSHOT_TS)

    selection = select_futures_chain_contracts(
        frame,
        query="cny",
        include_secids=["CNYRUBF", "CRU6"],
        exclude_secids=["CNYRUBF"],
    )

    assert [contract.secid for contract in selection.contracts] == ["CRU6"]


def test_secid_prefix_cr_filters_only_cr_family(futures_securities_response: dict) -> None:
    frame = normalize_futures_metadata(futures_securities_response, snapshot_ts=SNAPSHOT_TS)

    selection = select_futures_chain_contracts(frame, query="cny", secid_prefix="CR")

    assert selection.contracts
    assert all(contract.secid.startswith("CR") for contract in selection.contracts)
    assert {"MYU6", "UCU6", "CNYRUBF"}.isdisjoint(
        {contract.secid for contract in selection.contracts}
    )


def test_limit_behavior_reports_unselected_contracts(futures_securities_response: dict) -> None:
    frame = normalize_futures_metadata(futures_securities_response, snapshot_ts=SNAPSHOT_TS)

    selection = select_futures_chain_contracts(frame, query="cny", limit=2)

    assert len(selection.contracts) == 2
    assert any(skipped.reason == "not_selected_by_limit" for skipped in selection.skipped)


def test_skipped_contract_reporting_for_missing_board(futures_securities_response: dict) -> None:
    frame = normalize_futures_metadata(futures_securities_response, snapshot_ts=SNAPSHOT_TS)
    frame = frame.filter(frame["secid"] == "CNYRUBF").with_columns(
        pl.lit(None).cast(pl.Utf8).alias("board")
    )

    selection = select_futures_chain_contracts(frame, query="cny")

    assert selection.contracts_found == 1
    assert selection.contracts == []
    assert selection.skipped[0].secid == "CNYRUBF"
    assert selection.skipped[0].reason == "missing_board"


def test_derives_individual_contract_date_range_from_expiration() -> None:
    contract = FuturesChainContract(
        secid="CRU6",
        board="RFUD",
        expiration_date=date(2026, 9, 17),
        last_trade_date=date(2026, 9, 16),
    )

    date_range = derive_contract_date_range(
        contract,
        user_from_date="2015-01-01",
        user_till_date="2026-01-01",
        use_contract_date_ranges=True,
    )

    assert isinstance(date_range, FuturesContractDateRange)
    assert date_range.from_date == "2015-01-01"
    assert date_range.till_date == "2026-09-17"


def test_derives_user_date_range_when_contract_ranges_disabled() -> None:
    contract = FuturesChainContract(
        secid="CRU6",
        board="RFUD",
        expiration_date=date(2026, 9, 17),
    )

    date_range = derive_contract_date_range(
        contract,
        user_from_date="2015-01-01",
        user_till_date="2026-01-01",
        use_contract_date_ranges=False,
    )

    assert isinstance(date_range, FuturesContractDateRange)
    assert date_range.from_date == "2015-01-01"
    assert date_range.till_date == "2026-01-01"


def test_skips_expired_contract_before_from_date() -> None:
    contract = FuturesChainContract(
        secid="CRZ0",
        board="RFUD",
        expiration_date=date(2020, 12, 17),
    )

    skipped = derive_contract_date_range(
        contract,
        user_from_date="2023-01-01",
        user_till_date="2026-01-01",
        use_contract_date_ranges=True,
    )

    assert isinstance(skipped, FuturesBulkSkip)
    assert skipped.secid == "CRZ0"
    assert skipped.reason == "expired_before_from_date"


def test_bulk_result_summary(
    futures_securities_response: dict,
    futures_candles_response: dict,
    empty_candles_response: dict,
    tmp_path,
) -> None:
    client = FakeBulkFuturesClient(
        futures_securities_response,
        pages_by_symbol={"CNYRUBF": [futures_candles_response, empty_candles_response]},
    )

    result = prepare_futures_chain_data(
        query="cny",
        include_secids=["CNYRUBF"],
        timeframe="1d",
        from_date="2023-01-10",
        till_date="2023-01-20",
        save_raw=True,
        save_normalized=True,
        data_root=tmp_path,
        overwrite=True,
        client=client,  # type: ignore[arg-type]
        config=MoexIssConfig(max_pages=10),
    )
    summary = format_futures_bulk_summary(result)

    assert summary["contracts_found"] == 1
    assert summary["contracts_selected"] == 1
    assert summary["contracts_downloaded"] == 1
    assert summary["contracts_skipped"] == 0
    assert summary["successful_contracts"] == 1
    assert summary["failed_contracts"] == 0
    assert summary["rows_total"] == len(futures_candles_response["candles"]["data"])
    assert summary["downloaded_contracts"] == result.download_results
    assert result.meets_min_successful_contracts
    assert result.normalized_paths and result.normalized_paths[0].exists()


def test_no_empty_normalized_parquet_is_written_for_no_row_contract(
    futures_securities_response: dict,
    empty_candles_response: dict,
    tmp_path,
) -> None:
    client = FakeBulkFuturesClient(
        futures_securities_response,
        pages_by_symbol={"CRU6": [empty_candles_response]},
    )

    result = prepare_futures_chain_data(
        query="cny",
        include_secids=["CRU6"],
        timeframe="5m",
        from_date="2023-01-10",
        till_date="2023-01-20",
        save_raw=True,
        save_normalized=True,
        data_root=tmp_path,
        overwrite=True,
        client=client,  # type: ignore[arg-type]
        config=MoexIssConfig(max_pages=10),
    )

    candle_root = tmp_path / "normalized" / "candles"
    raw_candle_files = list((tmp_path / "raw" / "moex" / "candles").rglob("*.json"))

    assert result.contracts_downloaded == 0
    assert result.skipped_contracts[0].reason == "no_rows"
    assert raw_candle_files
    assert not candle_root.exists()


def test_bulk_5m_download_writes_timeframe_partition(
    futures_securities_response: dict,
    futures_candles_response: dict,
    empty_candles_response: dict,
    tmp_path,
) -> None:
    client = FakeBulkFuturesClient(
        futures_securities_response,
        pages_by_symbol={"CRU6": [futures_candles_response, empty_candles_response]},
    )

    result = prepare_futures_chain_data(
        query="cny",
        include_secids=["CRU6"],
        timeframe="5m",
        from_date="2023-01-10",
        till_date="2023-01-20",
        save_normalized=True,
        data_root=tmp_path,
        overwrite=True,
        client=client,  # type: ignore[arg-type]
        config=MoexIssConfig(max_pages=10),
    )

    normalized_path = result.normalized_paths[0]
    loaded = pl.read_parquet(normalized_path)

    assert "timeframe=5m" in normalized_path.as_posix()
    assert set(loaded["timeframe"].to_list()) == {"5m"}
