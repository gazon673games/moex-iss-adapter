from __future__ import annotations

from datetime import datetime

from typer.testing import CliRunner

from moex_iss_adapter.cli import app
from moex_iss_adapter.futures import parse_futures_securities
from moex_iss_adapter.metadata import normalize_futures_metadata
from moex_iss_adapter.models import (
    DownloadResult,
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
