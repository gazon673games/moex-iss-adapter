from __future__ import annotations

from datetime import datetime

from typer.testing import CliRunner

from moex_iss_adapter.cli import app
from moex_iss_adapter.metadata import normalize_futures_metadata


def test_cli_exposes_metadata_snapshots_subcommand(
    futures_securities_response: dict,
    tmp_path,
) -> None:
    frame = normalize_futures_metadata(
        futures_securities_response,
        snapshot_ts=datetime(2026, 7, 4, 12, 30, 45),
    )
    snapshot_dir = (
        tmp_path
        / "normalized"
        / "metadata"
        / "exchange=MOEX"
        / "engine=futures"
        / "market=forts"
        / "securities"
        / "snapshot_ts=20260704T123045Z"
    )
    snapshot_dir.mkdir(parents=True)
    frame.write_parquet(snapshot_dir / "part-000.parquet")

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["metadata", "snapshots", "--data-root", str(tmp_path), "--engine", "futures"],
    )

    assert result.exit_code == 0
    assert "EXCHANGE | ENGINE | MARKET | SNAPSHOT_TS | ROW_COUNT | PARQUET_PATH" in result.output
    assert "20260704T123045Z" in result.output
    assert "part-000.parquet" in result.output


def test_cli_metadata_snapshots_empty(tmp_path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["metadata", "snapshots", "--data-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "No metadata snapshots found." in result.output
