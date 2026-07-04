from __future__ import annotations

from datetime import date, datetime

from typer.testing import CliRunner

from moex_iss_adapter.cli import app
from moex_iss_adapter.futures import parse_futures_securities
from moex_iss_adapter.metadata import normalize_futures_metadata
from moex_iss_adapter.models import (
    DownloadResult,
    FuturesBulkResult,
    FuturesBulkSkip,
    FuturesChainContract,
    MetadataQualityReport,
    MetadataSnapshotResult,
    QualityReport,
)


def _quality_report() -> QualityReport:
    return QualityReport(
        passed=True,
        row_count=1,
        min_ts=datetime(2023, 1, 10),
        max_ts=datetime(2023, 1, 10),
        duplicate_count=0,
        issues=[],
    )


def test_cli_exposes_futures_search_subcommand(
    monkeypatch,
    futures_securities_response: dict,
) -> None:
    monkeypatch.setattr(
        "moex_iss_adapter.cli.futures.search_futures_securities",
        lambda **_kwargs: parse_futures_securities(futures_securities_response)[:2],
    )
    runner = CliRunner()

    result = runner.invoke(app, ["futures", "search", "--query", "CNY"])

    assert result.exit_code == 0
    assert "SECID | SHORTNAME | SECNAME | BOARDID | ASSETCODE | LASTTRADEDATE" in result.output
    assert "CNYRUBF" in result.output


def test_cli_filters_current_futures_search_by_secid_prefix(
    monkeypatch,
    futures_securities_response: dict,
) -> None:
    monkeypatch.setattr(
        "moex_iss_adapter.cli.futures.search_futures_securities",
        lambda **_kwargs: parse_futures_securities(futures_securities_response),
    )
    runner = CliRunner()

    result = runner.invoke(app, ["futures", "search", "--query", "CNY", "--secid-prefix", "CR"])

    assert result.exit_code == 0
    assert "CRU6" in result.output
    assert "MYU6" not in result.output
    assert "UCU6" not in result.output
    assert "CNYRUBF" not in result.output


def test_cli_search_include_expired_uses_historical_discovery(monkeypatch) -> None:
    def fake_search_historical_futures_contracts(**kwargs) -> list[FuturesChainContract]:
        assert kwargs["query"] == "CNY"
        assert kwargs["secid_prefix"] == "CR"
        return [
            FuturesChainContract(
                secid="CRH5",
                board="RFUD",
                shortname="CNY-3.25",
                secname="Futures contract CNY-3.25",
                assetcode="CNY",
                expiration_date=date(2025, 3, 20),
                last_trade_date=date(2025, 3, 20),
                source_endpoint="/securities/CRH5.json",
            )
        ]

    monkeypatch.setattr(
        "moex_iss_adapter.cli.futures.search_historical_futures_contracts",
        fake_search_historical_futures_contracts,
    )
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["futures", "search", "--query", "CNY", "--secid-prefix", "CR", "--include-expired"],
    )

    assert result.exit_code == 0
    assert "EXPIRATION_DATE" in result.output
    assert "CRH5 | RFUD | CNY-3.25" in result.output
    assert "/securities/CRH5.json" in result.output


def test_cli_searches_saved_futures_metadata_snapshot(
    futures_securities_response: dict,
    tmp_path,
) -> None:
    frame = normalize_futures_metadata(
        futures_securities_response,
        snapshot_ts=datetime(2026, 7, 4, 12, 30, 45),
    )
    metadata_path = tmp_path / "metadata.parquet"
    frame.write_parquet(metadata_path)
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["futures", "search", "--query", "CNY", "--metadata-path", str(metadata_path)],
    )

    assert result.exit_code == 0
    assert "CNYRUBF" in result.output


def test_cli_exposes_futures_snapshot_subcommand(monkeypatch, tmp_path) -> None:
    def fake_save_futures_metadata_snapshot(**kwargs) -> MetadataSnapshotResult:
        return MetadataSnapshotResult(
            engine="futures",
            market="forts",
            row_count=2,
            snapshot_ts=datetime(2026, 7, 4, 12, 30, 45),
            raw_path=tmp_path / "raw.json" if kwargs["save_raw"] else None,
            normalized_path=tmp_path / "part-000.parquet" if kwargs["save_normalized"] else None,
            quality_report=MetadataQualityReport(
                passed=True,
                row_count=2,
                duplicate_count=0,
                issues=[],
            ),
        )

    monkeypatch.setattr(
        "moex_iss_adapter.cli.futures.save_futures_metadata_snapshot",
        fake_save_futures_metadata_snapshot,
    )
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["futures", "snapshot", "--save-raw", "--save-normalized", "--data-root", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert "engine: futures" in result.output
    assert "market: forts" in result.output
    assert "row count: 2" in result.output
    assert "quality status: passed" in result.output


def test_cli_exposes_futures_candles_subcommand(monkeypatch) -> None:
    def fake_download_futures_candles(**kwargs) -> DownloadResult:
        return DownloadResult(
            symbol=kwargs["symbol"],
            engine="futures",
            market="forts",
            board=kwargs["board"] or "RFUD",
            timeframe=kwargs["timeframe"],
            from_date=kwargs["from_date"],
            till_date=kwargs["till_date"],
            row_count=1,
            min_ts=datetime(2023, 1, 10),
            max_ts=datetime(2023, 1, 10),
            raw_path=None,
            normalized_path=None,
            quality_report=_quality_report(),
        )

    monkeypatch.setattr(
        "moex_iss_adapter.cli.futures.download_futures_candles",
        fake_download_futures_candles,
    )
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "futures",
            "candles",
            "--symbol",
            "CNYRUBF",
            "--from-date",
            "2023-01-10",
            "--till-date",
            "2023-01-20",
        ],
    )

    assert result.exit_code == 0
    assert "symbol: CNYRUBF" in result.output
    assert "board: RFUD" in result.output
    assert "quality status: passed" in result.output


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
        "moex_iss_adapter.cli.futures.prepare_futures_chain_data",
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
        "moex_iss_adapter.cli.futures.prepare_futures_chain_data",
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
