from __future__ import annotations

from datetime import datetime

from typer.testing import CliRunner

from moex_iss_adapter.cli import app
from moex_iss_adapter.models import DownloadResult, QualityReport
from moex_iss_adapter.normalizers import normalize_candles


def _quality_report() -> QualityReport:
    return QualityReport(
        passed=True,
        row_count=1,
        min_ts=datetime(2023, 1, 10),
        max_ts=datetime(2023, 1, 10),
        duplicate_count=0,
        issues=[],
    )


def test_cli_exposes_candles_subcommand(monkeypatch) -> None:
    def fake_download_candles(**kwargs) -> DownloadResult:
        return DownloadResult(
            symbol=kwargs["symbol"],
            engine=kwargs["engine"],
            market=kwargs["market"],
            board=kwargs["board"],
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

    monkeypatch.setattr("moex_iss_adapter.cli.candles.download_candles", fake_download_candles)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "candles",
            "--symbol",
            "SBER",
            "--from-date",
            "2023-01-10",
            "--till-date",
            "2023-01-20",
        ],
    )

    assert result.exit_code == 0
    assert "symbol: SBER" in result.output
    assert "quality status: passed" in result.output


def test_cli_exposes_quality_subcommand(sber_candles_response: dict, tmp_path) -> None:
    frame = normalize_candles(
        [sber_candles_response],
        engine="stock",
        market="shares",
        board="TQBR",
        symbol="SBER",
        timeframe="1d",
    )
    parquet_path = tmp_path / "candles.parquet"
    frame.write_parquet(parquet_path)

    runner = CliRunner()
    result = runner.invoke(app, ["quality", str(parquet_path)])

    assert result.exit_code == 0
    assert "quality status: passed" in result.output
