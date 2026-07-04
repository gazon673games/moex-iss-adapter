"""Shared CLI output helpers."""

from __future__ import annotations

import logging

import typer

from moex_iss_adapter.models import DownloadResult, MetadataSnapshotResult, QualityReport


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.INFO if verbose else logging.WARNING)


def print_quality_issues(issues: list[str]) -> None:
    if not issues:
        return
    typer.echo("quality issues:")
    for issue in issues:
        typer.echo(f"- {issue}")


def print_download_result(result: DownloadResult) -> None:
    report = result.quality_report
    typer.echo(f"symbol: {result.symbol}")
    typer.echo(f"board: {result.board}")
    typer.echo(f"timeframe: {result.timeframe}")
    typer.echo(f"requested date range: {result.from_date} to {result.till_date}")
    typer.echo(f"row count: {result.row_count}")
    typer.echo(f"min ts: {result.min_ts}")
    typer.echo(f"max ts: {result.max_ts}")
    typer.echo(f"raw output path: {result.raw_path}")
    typer.echo(f"normalized output path: {result.normalized_path}")
    typer.echo(f"quality status: {'passed' if report.passed else 'failed'}")
    print_quality_issues(report.issues)


def print_metadata_snapshot_result(result: MetadataSnapshotResult) -> None:
    report = result.quality_report
    typer.echo(f"engine: {result.engine}")
    typer.echo(f"market: {result.market}")
    typer.echo(f"row count: {result.row_count}")
    typer.echo(f"snapshot timestamp: {result.snapshot_ts}")
    typer.echo(f"raw output path: {result.raw_path}")
    typer.echo(f"normalized output path: {result.normalized_path}")
    typer.echo(f"quality status: {'passed' if report.passed else 'failed'}")
    print_quality_issues(report.issues)


def print_candle_quality_report(parquet_path: object, report: QualityReport) -> None:
    typer.echo(f"parquet path: {parquet_path}")
    typer.echo(f"row count: {report.row_count}")
    typer.echo(f"min ts: {report.min_ts}")
    typer.echo(f"max ts: {report.max_ts}")
    typer.echo(f"duplicate count: {report.duplicate_count}")
    typer.echo(f"quality status: {'passed' if report.passed else 'failed'}")
    print_quality_issues(report.issues)
