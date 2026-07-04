from __future__ import annotations

from datetime import datetime

import polars as pl

from moex_iss_adapter.downloads.futures_bulk import (
    format_futures_bulk_summary,
    prepare_futures_chain_data,
    select_futures_chain_contracts,
)
from moex_iss_adapter.metadata import normalize_futures_metadata
from moex_iss_adapter.models import MoexIssConfig

SNAPSHOT_TS = datetime(2026, 7, 4, 12, 30, 45)


class FakeBulkFuturesClient:
    def __init__(self, securities_response: dict, pages_by_symbol: dict[str, list[dict]]) -> None:
        self.securities_response = securities_response
        self.pages_by_symbol = pages_by_symbol
        self.requested_symbols: list[str] = []

    def get_market_securities(self, engine: str, market: str) -> dict:
        assert engine == "futures"
        assert market == "forts"
        return self.securities_response

    def get_candles_page(self, **kwargs) -> dict:
        symbol = kwargs["security"]
        self.requested_symbols.append(symbol)
        pages = self.pages_by_symbol[symbol]
        if len(pages) == 1:
            return pages[0]
        return pages.pop(0)


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


def test_limit_behavior_reports_unselected_contracts(futures_securities_response: dict) -> None:
    frame = normalize_futures_metadata(futures_securities_response, snapshot_ts=SNAPSHOT_TS)

    selection = select_futures_chain_contracts(frame, query="cny", limit=2)

    assert len(selection.contracts) == 2
    assert any(skipped.reason == "not selected by limit" for skipped in selection.skipped)


def test_skipped_contract_reporting_for_missing_board(futures_securities_response: dict) -> None:
    frame = normalize_futures_metadata(futures_securities_response, snapshot_ts=SNAPSHOT_TS)
    frame = frame.filter(frame["secid"] == "CNYRUBF").with_columns(
        pl.lit(None).cast(pl.Utf8).alias("board")
    )

    selection = select_futures_chain_contracts(frame, query="cny")

    assert selection.contracts_found == 1
    assert selection.contracts == []
    assert selection.skipped[0].secid == "CNYRUBF"
    assert selection.skipped[0].reason == "missing board"


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
    assert summary["rows_total"] == len(futures_candles_response["candles"]["data"])
    assert result.normalized_paths and result.normalized_paths[0].exists()


def test_prepare_chain_data_handles_empty_matches(
    futures_securities_response: dict,
    tmp_path,
) -> None:
    client = FakeBulkFuturesClient(futures_securities_response, pages_by_symbol={})

    result = prepare_futures_chain_data(
        query="NOT_A_REAL_CNY_CONTRACT",
        from_date="2023-01-10",
        till_date="2023-01-20",
        data_root=tmp_path,
        client=client,  # type: ignore[arg-type]
    )

    assert result.contracts_found == 0
    assert result.contracts_selected == 0
    assert result.contracts_downloaded == 0
    assert result.rows_total == 0
    assert client.requested_symbols == []


def test_prepare_chain_data_continues_after_one_failed_download(
    futures_securities_response: dict,
    futures_candles_response: dict,
    empty_candles_response: dict,
    malformed_response: dict,
    tmp_path,
) -> None:
    client = FakeBulkFuturesClient(
        futures_securities_response,
        pages_by_symbol={
            "CNYRUBF": [futures_candles_response, empty_candles_response],
            "CRU6": [malformed_response],
        },
    )

    result = prepare_futures_chain_data(
        query="cny",
        include_secids=["CNYRUBF", "CRU6"],
        from_date="2023-01-10",
        till_date="2023-01-20",
        data_root=tmp_path,
        client=client,  # type: ignore[arg-type]
        config=MoexIssConfig(max_pages=10),
    )

    assert result.contracts_selected == 2
    assert result.contracts_downloaded == 1
    assert result.download_results[0].symbol == "CNYRUBF"
    assert any(
        skipped.secid == "CRU6" and skipped.reason.startswith("download failed")
        for skipped in result.skipped_contracts
    )
