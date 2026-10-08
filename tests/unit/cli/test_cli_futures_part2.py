from __future__ import annotations

from datetime import datetime

from tests.unit.cli.test_cli_futures_support import _quality_report
from typer.testing import CliRunner

from moex_iss_adapter.cli import app
from moex_iss_adapter.models import (
    DownloadResult,
    FuturesBulkResult,
    FuturesBulkSkip,
    FuturesChainContract,
    MetadataQualityReport,
    MetadataSnapshotResult,
)


def test_cli_exposes_futures_prepare_chain_data_subcommand(monkeypatch, tmp_path) -> None:
    def fake_prepare_futures_chain_data(**kwargs) -> FuturesBulkResult:
        download = DownloadResult(
            symbol="CNYRUBF",
            engine="futures",
            market="forts",
            board="RFUD",
            timeframe=kwargs["timeframe"],
            from_date=kwargs["from_date"],
            till_date=kwargs["till_date"],
            row_count=1,
            min_ts=datetime(2023, 1, 10),
            max_ts=datetime(2023, 1, 10),
            raw_path=None,
            normalized_path=tmp_path / "part-000.parquet",
            quality_report=_quality_report(),
        )
        return FuturesBulkResult(
            metadata_snapshot=MetadataSnapshotResult(
                engine="futures",
                market="forts",
                row_count=2,
                snapshot_ts=datetime(2026, 7, 4, 12, 30, 45),
                raw_path=None,
                normalized_path=tmp_path / "metadata.parquet",
                quality_report=MetadataQualityReport(
                    passed=True,
                    row_count=2,
                    duplicate_count=0,
                    issues=[],
                ),
            ),
            contracts_found=2,
            min_successful_contracts=kwargs["min_successful_contracts"],
            selected_contracts=[
                FuturesChainContract(secid="CNYRUBF", board="RFUD"),
                FuturesChainContract(secid="CRU6", board="RFUD"),
            ],
            download_results=[download],
            skipped_contracts=[
                FuturesBulkSkip(
                    secid="CRU6",
                    board="RFUD",
                    reason="no_rows",
                    metadata_found=True,
                    candles_found=False,
                    row_count=0,
                )
            ],
        )

    monkeypatch.setattr(
        "moex_iss_adapter.cli._futures_prepare.prepare_futures_chain_data",
        fake_prepare_futures_chain_data,
    )
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "futures",
            "prepare-chain-data",
            "--query",
            "CNY",
            "--timeframe",
            "1d",
            "--from-date",
            "2023-01-10",
            "--till-date",
            "2023-01-20",
            "--data-root",
            str(tmp_path),
            "--use-contract-date-ranges",
        ],
    )

    assert result.exit_code == 0
    assert "metadata_snapshot_ts: 20260704T123045Z" in result.output
    assert "contracts_downloaded: 1" in result.output
    assert "successful_contracts: 1" in result.output
    assert "rows_total: 1" in result.output
    assert "metadata_found: True" in result.output
    assert "candles_found: True" in result.output
    assert "candles_found: False" in result.output
    assert "row_count: 0" in result.output
    assert "from_date_used: 2023-01-10" in result.output
    assert "till_date_used: 2023-01-20" in result.output
    assert "CRU6@RFUD: no_rows" in result.output
    assert "CNYRUBF@RFUD: passed" in result.output


def test_cli_prepare_chain_data_exits_nonzero_when_min_successful_not_met(
    monkeypatch,
    tmp_path,
) -> None:
    def fake_prepare_futures_chain_data(**kwargs) -> FuturesBulkResult:
        download = DownloadResult(
            symbol="CNYRUBF",
            engine="futures",
            market="forts",
            board="RFUD",
            timeframe=kwargs["timeframe"],
            from_date=kwargs["from_date"],
            till_date=kwargs["till_date"],
            row_count=1,
            min_ts=datetime(2023, 1, 10),
            max_ts=datetime(2023, 1, 10),
            raw_path=None,
            normalized_path=tmp_path / "part-000.parquet",
            quality_report=_quality_report(),
        )
        return FuturesBulkResult(
            metadata_snapshot=MetadataSnapshotResult(
                engine="futures",
                market="forts",
                row_count=1,
                snapshot_ts=datetime(2026, 7, 4, 12, 30, 45),
                raw_path=None,
                normalized_path=None,
                quality_report=MetadataQualityReport(
                    passed=True,
                    row_count=1,
                    duplicate_count=0,
                    issues=[],
                ),
            ),
            contracts_found=1,
            min_successful_contracts=kwargs["min_successful_contracts"],
            selected_contracts=[FuturesChainContract(secid="CNYRUBF", board="RFUD")],
            download_results=[download],
            skipped_contracts=[],
        )

    monkeypatch.setattr(
        "moex_iss_adapter.cli._futures_prepare.prepare_futures_chain_data",
        fake_prepare_futures_chain_data,
    )
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "futures",
            "prepare-chain-data",
            "--query",
            "CNY",
            "--from-date",
            "2023-01-10",
            "--till-date",
            "2023-01-20",
            "--min-successful-contracts",
            "2",
        ],
    )

    assert result.exit_code == 1
    assert "below --min-successful-contracts (2)" in result.output
    assert "needs at least 2 concrete contracts" in result.output
