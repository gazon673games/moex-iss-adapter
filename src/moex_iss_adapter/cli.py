"""Typer CLI for the MOEX ISS adapter."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import polars as pl
import typer

from moex_iss_adapter.constants import (
    DEFAULT_BOARD,
    DEFAULT_ENGINE,
    DEFAULT_FUTURES_ENGINE,
    DEFAULT_FUTURES_MARKET,
    DEFAULT_MARKET,
    DEFAULT_TIMEFRAME,
)
from moex_iss_adapter.downloader import (
    download_candles,
    download_futures_candles,
    save_futures_metadata_snapshot,
    search_futures_securities,
    search_saved_futures_metadata,
)
from moex_iss_adapter.exceptions import MoexIssAdapterError
from moex_iss_adapter.models import DownloadResult
from moex_iss_adapter.quality import validate_candles
from moex_iss_adapter.storage import list_metadata_snapshots

app = typer.Typer(help="MOEX ISS OHLCV adapter commands.")
futures_app = typer.Typer(help="MOEX futures discovery and candle commands.")
metadata_app = typer.Typer(help="Saved metadata snapshot commands.")
app.add_typer(futures_app, name="futures")
app.add_typer(metadata_app, name="metadata")


@app.callback()
def main() -> None:
    """Run MOEX ISS adapter commands."""


@app.command()
def candles(
    symbol: Annotated[str, typer.Option("--symbol", help="Security code, for example SBER")],
    from_date: Annotated[str, typer.Option("--from-date", help="Start date in YYYY-MM-DD")],
    till_date: Annotated[str, typer.Option("--till-date", help="End date in YYYY-MM-DD")],
    engine: Annotated[str, typer.Option("--engine")] = DEFAULT_ENGINE,
    market: Annotated[str, typer.Option("--market")] = DEFAULT_MARKET,
    board: Annotated[str, typer.Option("--board")] = DEFAULT_BOARD,
    timeframe: Annotated[str, typer.Option("--timeframe")] = DEFAULT_TIMEFRAME,
    save_raw: Annotated[bool, typer.Option("--save-raw")] = False,
    save_normalized: Annotated[bool, typer.Option("--save-normalized")] = False,
    data_root: Annotated[Path, typer.Option("--data-root")] = Path("data"),
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
) -> None:
    """Download, normalize, store, and quality-check candle data."""

    logging.basicConfig(level=logging.INFO if verbose else logging.WARNING)

    try:
        result = download_candles(
            symbol=symbol,
            engine=engine,
            market=market,
            board=board,
            timeframe=timeframe,
            from_date=from_date,
            till_date=till_date,
            save_raw=save_raw,
            save_normalized=save_normalized,
            data_root=data_root,
            overwrite=overwrite,
        )
    except MoexIssAdapterError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    _print_download_result(result)


def _print_download_result(result: DownloadResult) -> None:
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
    if report.issues:
        typer.echo("quality issues:")
        for issue in report.issues:
            typer.echo(f"- {issue}")


@futures_app.command("search")
def futures_search(
    query: Annotated[
        str | None,
        typer.Option("--query", help="Search across SECID/name fields"),
    ] = None,
    secid: Annotated[
        str | None,
        typer.Option("--secid", help="Filter by SECID"),
    ] = None,
    asset_code: Annotated[
        str | None,
        typer.Option("--asset-code", help="Filter by ASSETCODE"),
    ] = None,
    short_name: Annotated[
        str | None,
        typer.Option("--short-name", help="Filter by SHORTNAME"),
    ] = None,
    security_name: Annotated[
        str | None,
        typer.Option("--security-name", help="Filter by SECNAME"),
    ] = None,
    metadata_path: Annotated[
        Path | None,
        typer.Option("--metadata-path", help="Saved normalized metadata Parquet snapshot"),
    ] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, help="Maximum rows to print")] = 25,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
) -> None:
    """Search available MOEX futures contracts."""

    logging.basicConfig(level=logging.INFO if verbose else logging.WARNING)
    try:
        results = (
            search_saved_futures_metadata(
                metadata_path=metadata_path,
                query=query,
                secid=secid,
                asset_code=asset_code,
                short_name=short_name,
                security_name=security_name,
            )
            if metadata_path is not None
            else search_futures_securities(
                query=query,
                secid=secid,
                asset_code=asset_code,
                short_name=short_name,
                security_name=security_name,
                engine=DEFAULT_FUTURES_ENGINE,
                market=DEFAULT_FUTURES_MARKET,
            )
        )
    except MoexIssAdapterError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if not results:
        typer.echo("No futures securities matched the search.")
        return

    typer.echo("SECID | SHORTNAME | SECNAME | BOARDID | ASSETCODE | LASTTRADEDATE")
    for security in results[:limit]:
        typer.echo(
            " | ".join(
                (
                    security.secid,
                    security.shortname or "",
                    security.secname or "",
                    security.boardid or "",
                    security.assetcode or "",
                    security.lasttradedate or security.lastdeldate or "",
                )
            )
        )


@futures_app.command("snapshot")
def futures_snapshot(
    save_raw: Annotated[bool, typer.Option("--save-raw")] = False,
    save_normalized: Annotated[bool, typer.Option("--save-normalized")] = False,
    data_root: Annotated[Path, typer.Option("--data-root")] = Path("data"),
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
) -> None:
    """Fetch and optionally save a futures securities metadata snapshot."""

    logging.basicConfig(level=logging.INFO if verbose else logging.WARNING)
    try:
        result = save_futures_metadata_snapshot(
            save_raw=save_raw,
            save_normalized=save_normalized,
            data_root=data_root,
            overwrite=overwrite,
        )
    except MoexIssAdapterError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    report = result.quality_report
    typer.echo(f"engine: {result.engine}")
    typer.echo(f"market: {result.market}")
    typer.echo(f"row count: {result.row_count}")
    typer.echo(f"snapshot timestamp: {result.snapshot_ts}")
    typer.echo(f"raw output path: {result.raw_path}")
    typer.echo(f"normalized output path: {result.normalized_path}")
    typer.echo(f"quality status: {'passed' if report.passed else 'failed'}")
    if report.issues:
        typer.echo("quality issues:")
        for issue in report.issues:
            typer.echo(f"- {issue}")


@futures_app.command("candles")
def futures_candles(
    symbol: Annotated[str, typer.Option("--symbol", help="Concrete futures SECID")],
    from_date: Annotated[str, typer.Option("--from-date", help="Start date in YYYY-MM-DD")],
    till_date: Annotated[str, typer.Option("--till-date", help="End date in YYYY-MM-DD")],
    board: Annotated[
        str | None,
        typer.Option("--board", help="Futures BOARDID, for example RFUD; discovered if omitted"),
    ] = None,
    timeframe: Annotated[str, typer.Option("--timeframe")] = DEFAULT_TIMEFRAME,
    save_raw: Annotated[bool, typer.Option("--save-raw")] = False,
    save_normalized: Annotated[bool, typer.Option("--save-normalized")] = False,
    data_root: Annotated[Path, typer.Option("--data-root")] = Path("data"),
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
) -> None:
    """Download candles for one concrete MOEX futures contract."""

    logging.basicConfig(level=logging.INFO if verbose else logging.WARNING)
    try:
        result = download_futures_candles(
            symbol=symbol,
            board=board,
            timeframe=timeframe,
            from_date=from_date,
            till_date=till_date,
            save_raw=save_raw,
            save_normalized=save_normalized,
            data_root=data_root,
            overwrite=overwrite,
        )
    except MoexIssAdapterError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    _print_download_result(result)


@metadata_app.command("snapshots")
def metadata_snapshots(
    data_root: Annotated[Path, typer.Option("--data-root")] = Path("data"),
    engine: Annotated[str | None, typer.Option("--engine", help="Filter by engine")] = None,
    market: Annotated[str | None, typer.Option("--market", help="Filter by market")] = None,
    no_row_count: Annotated[
        bool,
        typer.Option("--no-row-count", help="Do not read row counts from Parquet files"),
    ] = False,
) -> None:
    """List saved normalized metadata snapshot Parquet files."""

    snapshots = list_metadata_snapshots(
        data_root=data_root,
        engine=engine,
        market=market,
        include_row_count=not no_row_count,
    )
    if not snapshots:
        typer.echo("No metadata snapshots found.")
        return

    typer.echo("EXCHANGE | ENGINE | MARKET | SNAPSHOT_TS | ROW_COUNT | PARQUET_PATH")
    for snapshot in snapshots:
        row_count = "" if snapshot.row_count is None else str(snapshot.row_count)
        typer.echo(
            " | ".join(
                (
                    snapshot.exchange,
                    snapshot.engine,
                    snapshot.market,
                    snapshot.snapshot_ts,
                    row_count,
                    str(snapshot.parquet_path),
                )
            )
        )


@app.command()
def quality(
    parquet_path: Annotated[Path, typer.Argument(help="Normalized candles Parquet file")],
) -> None:
    """Run quality checks for a normalized candle Parquet file."""

    try:
        frame = pl.read_parquet(parquet_path)
        report = validate_candles(frame)
    except Exception as exc:
        typer.echo(f"Error: failed to run quality checks for {parquet_path}: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"parquet path: {parquet_path}")
    typer.echo(f"row count: {report.row_count}")
    typer.echo(f"min ts: {report.min_ts}")
    typer.echo(f"max ts: {report.max_ts}")
    typer.echo(f"duplicate count: {report.duplicate_count}")
    typer.echo(f"quality status: {'passed' if report.passed else 'failed'}")
    if report.issues:
        typer.echo("quality issues:")
        for issue in report.issues:
            typer.echo(f"- {issue}")
