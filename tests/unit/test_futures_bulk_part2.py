from __future__ import annotations

from tests.unit.test_futures_bulk_support import FakeBulkFuturesClient

from moex_iss_adapter.downloads.futures_bulk import (
    format_futures_bulk_summary,
    prepare_futures_chain_data,
)
from moex_iss_adapter.models import (
    MoexIssConfig,
)


def test_manual_include_secid_downloads_without_metadata_row(
    futures_securities_response: dict,
    futures_candles_response: dict,
    empty_candles_response: dict,
    tmp_path,
) -> None:
    client = FakeBulkFuturesClient(
        futures_securities_response,
        pages_by_symbol={"CRH5": [futures_candles_response, empty_candles_response]},
    )

    result = prepare_futures_chain_data(
        include_secids=["CRH5"],
        from_date="2025-01-01",
        till_date="2025-03-31",
        save_normalized=True,
        data_root=tmp_path,
        overwrite=True,
        client=client,  # type: ignore[arg-type]
        config=MoexIssConfig(max_pages=10),
    )

    assert result.contracts_selected == 1
    assert result.selected_contracts[0].secid == "CRH5"
    assert result.selected_contracts[0].metadata_found is False
    assert result.download_results[0].symbol == "CRH5"
    assert result.download_results[0].row_count == len(futures_candles_response["candles"]["data"])


def test_no_row_expired_manual_secid_reports_status_without_empty_parquet(
    futures_securities_response: dict,
    empty_candles_response: dict,
    tmp_path,
) -> None:
    client = FakeBulkFuturesClient(
        futures_securities_response,
        pages_by_symbol={"CRH5": [empty_candles_response]},
    )

    result = prepare_futures_chain_data(
        include_secids=["CRH5"],
        from_date="2025-01-01",
        till_date="2025-03-31",
        save_raw=True,
        save_normalized=True,
        data_root=tmp_path,
        overwrite=True,
        client=client,  # type: ignore[arg-type]
        config=MoexIssConfig(max_pages=10),
    )

    skipped = result.skipped_contracts[0]
    assert result.contracts_downloaded == 0
    assert skipped.secid == "CRH5"
    assert skipped.reason == "no_rows"
    assert skipped.metadata_found is False
    assert skipped.candles_found is False
    assert skipped.row_count == 0
    assert not (tmp_path / "normalized" / "candles").exists()
    assert list((tmp_path / "raw" / "moex" / "candles").rglob("*.json"))


def test_min_successful_contracts_passes(
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
        min_successful_contracts=1,
        from_date="2023-01-10",
        till_date="2023-01-20",
        data_root=tmp_path,
        client=client,  # type: ignore[arg-type]
        config=MoexIssConfig(max_pages=10),
    )

    assert result.successful_contracts == 1
    assert result.meets_min_successful_contracts


def test_min_successful_contracts_fails(
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
        min_successful_contracts=2,
        from_date="2023-01-10",
        till_date="2023-01-20",
        data_root=tmp_path,
        client=client,  # type: ignore[arg-type]
        config=MoexIssConfig(max_pages=10),
    )

    assert result.successful_contracts == 1
    assert result.failed_contracts == 0
    assert not result.meets_min_successful_contracts


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
        skipped.secid == "CRU6" and skipped.reason.startswith("download_failed")
        for skipped in result.skipped_contracts
    )


def test_report_includes_per_contract_date_ranges_and_skipped_reasons(
    futures_securities_response: dict,
    futures_candles_response: dict,
    empty_candles_response: dict,
    tmp_path,
) -> None:
    client = FakeBulkFuturesClient(
        futures_securities_response,
        pages_by_symbol={
            "CNYRUBF": [futures_candles_response, empty_candles_response],
            "CRU6": [empty_candles_response],
        },
    )

    result = prepare_futures_chain_data(
        query="cny",
        include_secids=["CNYRUBF", "CRU6"],
        from_date="2015-01-01",
        till_date="2026-01-01",
        use_contract_date_ranges=True,
        data_root=tmp_path,
        client=client,  # type: ignore[arg-type]
        config=MoexIssConfig(max_pages=10),
    )
    summary = format_futures_bulk_summary(result)
    downloaded = summary["downloaded_contracts"][0]
    skipped = summary["skipped_contracts"][0]

    assert downloaded.symbol == "CNYRUBF"
    assert downloaded.from_date == "2015-01-01"
    assert downloaded.till_date == "2100-01-01"
    assert skipped.secid == "CRU6"
    assert skipped.reason == "no_rows"
