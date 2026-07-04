from __future__ import annotations

import pytest

from moex_iss_adapter.downloader import prepare_futures_chain_data
from moex_iss_adapter.exceptions import MoexHttpError
from moex_iss_adapter.models import MoexIssConfig


@pytest.mark.integration
def test_prepare_live_cny_futures_chain_data(tmp_path) -> None:
    config = MoexIssConfig(timeout_seconds=10.0, max_retries=1, max_pages=10)
    try:
        result = prepare_futures_chain_data(
            query="CNY",
            timeframe="1d",
            from_date="2026-07-01",
            till_date="2026-07-03",
            limit=3,
            use_contract_date_ranges=True,
            min_successful_contracts=1,
            save_raw=True,
            save_normalized=True,
            data_root=tmp_path,
            overwrite=True,
            config=config,
        )
    except MoexHttpError as exc:
        pytest.skip(f"MOEX ISS is not reachable from this environment: {exc}")

    if result.contracts_found == 0:
        pytest.skip("No CNY/RUB-related futures contracts are currently available from MOEX ISS")
    if result.contracts_downloaded == 0:
        pytest.skip("MOEX ISS returned no candle rows for the selected CNY futures contracts")

    assert result.metadata_snapshot.quality_report.passed
    assert result.contracts_selected > 0
    assert result.rows_total > 0
    assert all(download.quality_report.passed for download in result.download_results)
    assert result.metadata_snapshot.normalized_path is not None
    assert result.metadata_snapshot.normalized_path.exists()
    assert all(path.exists() for path in result.normalized_paths)


@pytest.mark.integration
def test_prepare_live_expired_cr_futures_contract(tmp_path) -> None:
    config = MoexIssConfig(timeout_seconds=10.0, max_retries=1, max_pages=10)
    try:
        result = prepare_futures_chain_data(
            include_secids=["CRH5"],
            timeframe="1d",
            from_date="2025-03-03",
            till_date="2025-03-07",
            use_contract_date_ranges=True,
            min_successful_contracts=1,
            save_raw=True,
            save_normalized=True,
            data_root=tmp_path,
            overwrite=True,
            config=config,
        )
    except MoexHttpError as exc:
        pytest.skip(f"MOEX ISS is not reachable from this environment: {exc}")

    if result.contracts_downloaded == 0:
        pytest.skip("MOEX ISS returned no candle rows for expired CRH5")

    assert result.selected_contracts[0].secid == "CRH5"
    assert result.download_results[0].symbol == "CRH5"
    assert result.download_results[0].quality_report.passed
    assert result.download_results[0].row_count > 0
    assert all(path.exists() for path in result.normalized_paths)
