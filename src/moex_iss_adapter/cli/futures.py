"""Futures CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from moex_iss_adapter.cli.common import (
    configure_logging,
    print_download_result,
    print_metadata_snapshot_result,
)
from moex_iss_adapter.constants import (
    DEFAULT_FUTURES_ENGINE,
    DEFAULT_FUTURES_MARKET,
    DEFAULT_TIMEFRAME,
)
from moex_iss_adapter.downloads.futures import (
    download_futures_candles,
    search_futures_securities,
    search_saved_futures_metadata,
)
from moex_iss_adapter.downloads.futures_metadata import save_futures_metadata_snapshot
from moex_iss_adapter.exceptions import MoexIssAdapterError

futures_app = typer.Typer(help="MOEX futures discovery and candle commands.")


@futures_app.command("search")
def futures_search(
    query: Annotated[
        str | None,
        typer.Option("--query", help="Search across SECID/name fields"),
    ] = None,
    secid: Annotated[str | None, typer.Option("--secid", help="Filter by SECID")] = None,
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

    configure_logging(verbose)
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

    configure_logging(verbose)
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

    print_metadata_snapshot_result(result)


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

    configure_logging(verbose)
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

    print_download_result(result)
