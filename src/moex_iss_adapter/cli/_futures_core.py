"""Futures CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from moex_iss_adapter.diagnostics import (
    find_normalized_candle_paths,
    write_intraday_coverage_report,
)
from moex_iss_adapter.downloads.futures_bulk import (
    format_futures_bulk_summary,
)
from moex_iss_adapter.models import FuturesBulkResult

futures_app = typer.Typer(help="MOEX futures discovery and candle commands.")


@futures_app.command("coverage-report")
def futures_coverage_report(
    timeframe: Annotated[str, typer.Option("--timeframe")] = "5m",
    secid_prefix: Annotated[
        str | None,
        typer.Option("--secid-prefix", help="Keep SECIDs starting with this prefix"),
    ] = None,
    board: Annotated[str, typer.Option("--board")] = "RFUD",
    data_root: Annotated[Path, typer.Option("--data-root")] = Path("data"),
    output_path: Annotated[
        Path,
        typer.Option("--output-path", help="Coverage diagnostics JSON output path."),
    ] = Path("data/reports/futures_5m_cny_cr_coverage.json"),
    csv_path: Annotated[
        Path | None,
        typer.Option("--csv-path", help="Optional coverage diagnostics CSV output path."),
    ] = None,
) -> None:
    """Write intraday coverage diagnostics for saved normalized futures candles."""

    paths = find_normalized_candle_paths(
        data_root=data_root,
        board=board,
        timeframe=timeframe,
        symbol_prefix=secid_prefix,
    )
    report = write_intraday_coverage_report(paths, json_path=output_path, csv_path=csv_path)
    typer.echo(f"coverage_report_path: {output_path}")
    if csv_path is not None:
        typer.echo(f"coverage_report_csv_path: {csv_path}")
    typer.echo(f"coverage_report_contracts: {report['summary']['contracts_reported']}")
    typer.echo(f"coverage_report_total_rows: {report['summary']['total_rows']}")


def _print_prepare_chain_data_result(result: FuturesBulkResult) -> None:
    summary = format_futures_bulk_summary(result)
    selected_by_secid = {contract.secid: contract for contract in result.selected_contracts}
    typer.echo(f"metadata_snapshot_ts: {summary['metadata_snapshot_ts']}")
    typer.echo(f"contracts_found: {summary['contracts_found']}")
    typer.echo(f"contracts_selected: {summary['contracts_selected']}")
    typer.echo(f"contracts_downloaded: {summary['contracts_downloaded']}")
    typer.echo(f"contracts_skipped: {summary['contracts_skipped']}")
    typer.echo(f"successful_contracts: {summary['successful_contracts']}")
    typer.echo(f"failed_contracts: {summary['failed_contracts']}")
    typer.echo(f"rows_total: {summary['rows_total']}")

    typer.echo("downloaded_contracts:")
    if result.download_results:
        for download in result.download_results:
            contract = selected_by_secid.get(download.symbol)
            typer.echo(f"- secid: {download.symbol}")
            typer.echo(f"  board: {download.board}")
            typer.echo(f"  metadata_found: {contract.metadata_found if contract else None}")
            typer.echo("  candles_found: True")
            typer.echo(f"  from_date_used: {download.from_date}")
            typer.echo(f"  till_date_used: {download.till_date}")
            typer.echo(f"  row_count: {download.row_count}")
            typer.echo(f"  min_ts: {download.min_ts}")
            typer.echo(f"  max_ts: {download.max_ts}")
            typer.echo(f"  normalized_path: {download.normalized_path}")
    else:
        typer.echo("- none")

    typer.echo("skipped_contracts:")
    if result.skipped_contracts:
        for skipped in result.skipped_contracts:
            label = skipped.secid or "<unknown>"
            if skipped.board:
                label = f"{label}@{skipped.board}"
            typer.echo(f"- {label}: {skipped.reason}")
            typer.echo(f"  metadata_found: {skipped.metadata_found}")
            typer.echo(f"  candles_found: {skipped.candles_found}")
            typer.echo(f"  row_count: {skipped.row_count}")
    else:
        typer.echo("- none")

    typer.echo("quality_results:")
    if result.download_results:
        for download in result.download_results:
            status = "passed" if download.quality_report.passed else "failed"
            typer.echo(
                f"- {download.symbol}@{download.board}: {status}, "
                f"rows={download.row_count}, min_ts={download.min_ts}, max_ts={download.max_ts}"
            )
    else:
        typer.echo("- none")
