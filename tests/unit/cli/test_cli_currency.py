from __future__ import annotations

from datetime import datetime

from typer.testing import CliRunner

from moex_iss_adapter.cli import app
from moex_iss_adapter.currency import parse_currency_securities
from moex_iss_adapter.models import DownloadResult, QualityReport


def _quality_report() -> QualityReport:
    return QualityReport(
        passed=True,
        row_count=1,
        min_ts=datetime(2023, 1, 10),
        max_ts=datetime(2023, 1, 10),
        duplicate_count=0,
        issues=[],
    )


def test_cli_exposes_currency_search_subcommand(
    monkeypatch,
    currency_securities_response: dict,
) -> None:
    monkeypatch.setattr(
        "moex_iss_adapter.cli.currency.search_currency_securities",
        lambda **_kwargs: parse_currency_securities(currency_securities_response)[:2],
    )
    runner = CliRunner()

    result = runner.invoke(app, ["currency", "search", "--query", "CNY"])

    assert result.exit_code == 0
    assert "SECID | SHORTNAME | SECNAME | BOARDID | FACEUNIT | CURRENCYID" in result.output
    assert "CNY000000TOD" in result.output


def test_cli_exposes_currency_candles_subcommand(monkeypatch) -> None:
    def fake_download_currency_candles(**kwargs) -> DownloadResult:
        return DownloadResult(
            symbol=kwargs["symbol"],
            engine="currency",
            market="selt",
            board=kwargs["board"] or "CETS",
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
        "moex_iss_adapter.cli.currency.download_currency_candles",
        fake_download_currency_candles,
    )
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "currency",
            "candles",
            "--symbol",
            "CNY000000TOD",
            "--from-date",
            "2023-01-10",
            "--till-date",
            "2023-01-20",
        ],
    )

    assert result.exit_code == 0
    assert "symbol: CNY000000TOD" in result.output
    assert "board: CETS" in result.output
    assert "quality status: passed" in result.output
