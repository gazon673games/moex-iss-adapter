"""Futures CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from moex_iss_adapter.cli._futures_core import (
    _print_prepare_chain_data_result,
    futures_app,
)
from moex_iss_adapter.cli.common import (
    configure_logging,
)
from moex_iss_adapter.constants import (
    DEFAULT_TIMEFRAME,
)
from moex_iss_adapter.diagnostics import (
    write_intraday_coverage_report,
)
from moex_iss_adapter.exceptions import MoexIssAdapterError


@futures_app.command("prepare-chain-data")
def futures_prepare_chain_data(
    from_date: Annotated[str, typer.Option("--from-date", help="Start date in YYYY-MM-DD")],
    till_date: Annotated[str, typer.Option("--till-date", help="End date in YYYY-MM-DD")],
    query: Annotated[
        str | None,
        typer.Option("--query", help="Search across SECID/name/asset-code fields"),
    ] = None,
    timeframe: Annotated[str, typer.Option("--timeframe")] = DEFAULT_TIMEFRAME,
    asset_code: Annotated[
        str | None,
        typer.Option("--asset-code", help="Filter by ASSETCODE"),
    ] = None,
    secid_prefix: Annotated[
        str | None,
        typer.Option("--secid-prefix", help="Keep SECIDs starting with this prefix"),
    ] = None,
    include_secid: Annotated[
        list[str] | None,
        typer.Option("--include-secid", help="Include only this SECID; repeatable"),
    ] = None,
    exclude_secid: Annotated[
        list[str] | None,
        typer.Option("--exclude-secid", help="Exclude this SECID; repeatable"),
    ] = None,
    limit: Annotated[
        int | None,
        typer.Option("--limit", min=1, help="Maximum selected contracts to download"),
    ] = None,
    board: Annotated[
        str | None,
        typer.Option("--board", help="Filter by futures BOARDID, for example RFUD"),
    ] = None,
    metadata_path: Annotated[
        Path | None,
        typer.Option("--metadata-path", help="Reuse a saved normalized metadata Parquet snapshot"),
    ] = None,
    include_expired: Annotated[
        bool,
        typer.Option("--include-expired", help="Search global ISS securities for expired futures"),
    ] = False,
    use_contract_date_ranges: Annotated[
        bool,
        typer.Option(
            "--use-contract-date-ranges",
            help="Use expiration/last-trade metadata to derive per-contract request ranges",
        ),
    ] = False,
    min_successful_contracts: Annotated[
        int,
        typer.Option(
            "--min-successful-contracts",
            min=1,
            help="Minimum quality-passing downloaded contracts required for exit code 0",
        ),
    ] = 1,
    save_raw: Annotated[bool, typer.Option("--save-raw")] = False,
    save_normalized: Annotated[bool, typer.Option("--save-normalized")] = False,
    data_root: Annotated[Path, typer.Option("--data-root")] = Path("data"),
    coverage_report_path: Annotated[
        Path | None,
        typer.Option(
            "--coverage-report-path",
            help="Write intraday coverage diagnostics JSON for downloaded normalized candles.",
        ),
    ] = None,
    coverage_report_csv_path: Annotated[
        Path | None,
        typer.Option(
            "--coverage-report-csv-path",
            help="Optionally write intraday coverage diagnostics CSV.",
        ),
    ] = None,
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
) -> None:
    """Prepare concrete futures candle data for downstream chain research."""

    configure_logging(verbose)
    try:
        result = _public_cli_module().prepare_futures_chain_data(
            query=query,
            timeframe=timeframe,
            from_date=from_date,
            till_date=till_date,
            asset_code=asset_code,
            secid_prefix=secid_prefix,
            include_secids=include_secid,
            exclude_secids=exclude_secid,
            limit=limit,
            board=board,
            metadata_path=metadata_path,
            use_contract_date_ranges=use_contract_date_ranges,
            include_expired=include_expired,
            min_successful_contracts=min_successful_contracts,
            save_raw=save_raw,
            save_normalized=save_normalized,
            data_root=data_root,
            overwrite=overwrite,
        )
    except MoexIssAdapterError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    _print_prepare_chain_data_result(result)
    if coverage_report_path is not None:
        report = write_intraday_coverage_report(
            result.normalized_paths,
            json_path=coverage_report_path,
            csv_path=coverage_report_csv_path,
        )
        typer.echo(f"coverage_report_path: {coverage_report_path}")
        if coverage_report_csv_path is not None:
            typer.echo(f"coverage_report_csv_path: {coverage_report_csv_path}")
        typer.echo(f"coverage_report_contracts: {report['summary']['contracts_reported']}")
        typer.echo(f"coverage_report_total_rows: {report['summary']['total_rows']}")
    if not result.meets_min_successful_contracts:
        downstream_note = (
            " Downstream continuous futures research needs at least 2 concrete contracts "
            "with candle data."
            if result.min_successful_contracts >= 2
            else ""
        )
        typer.echo(
            "Error: successful downloaded contracts "
            f"({result.successful_contracts}) is below --min-successful-contracts "
            f"({result.min_successful_contracts}).{downstream_note}",
            err=True,
        )
        raise typer.Exit(code=1)


def _public_cli_module():
    from moex_iss_adapter.cli import futures

    return futures
