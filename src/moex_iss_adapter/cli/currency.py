"""Currency CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from moex_iss_adapter.cli.common import configure_logging, print_download_result
from moex_iss_adapter.constants import (
    DEFAULT_CURRENCY_ENGINE,
    DEFAULT_CURRENCY_MARKET,
    DEFAULT_TIMEFRAME,
)
from moex_iss_adapter.downloads.currency import (
    download_currency_candles,
    search_currency_securities,
)
from moex_iss_adapter.exceptions import MoexIssAdapterError

currency_app = typer.Typer(help="MOEX currency discovery and candle commands.")


@currency_app.command("search")
def currency_search(
    query: Annotated[
        str | None,
        typer.Option("--query", help="Search across SECID/name/currency fields"),
    ] = None,
    secid: Annotated[str | None, typer.Option("--secid", help="Filter by SECID")] = None,
    short_name: Annotated[
        str | None,
        typer.Option("--short-name", help="Filter by SHORTNAME"),
    ] = None,
    security_name: Annotated[
        str | None,
        typer.Option("--security-name", help="Filter by SECNAME"),
    ] = None,
    face_unit: Annotated[
        str | None,
        typer.Option("--face-unit", help="Filter by FACEUNIT"),
    ] = None,
    currency_id: Annotated[
        str | None,
        typer.Option("--currency-id", help="Filter by CURRENCYID"),
    ] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, help="Maximum rows to print")] = 25,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
) -> None:
    """Search available MOEX currency instruments."""

    configure_logging(verbose)
    try:
        results = search_currency_securities(
            query=query,
            secid=secid,
            short_name=short_name,
            security_name=security_name,
            face_unit=face_unit,
            currency_id=currency_id,
            engine=DEFAULT_CURRENCY_ENGINE,
            market=DEFAULT_CURRENCY_MARKET,
        )
    except MoexIssAdapterError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if not results:
        typer.echo("No currency securities matched the search.")
        return

    typer.echo("SECID | SHORTNAME | SECNAME | BOARDID | FACEUNIT | CURRENCYID")
    for security in results[:limit]:
        typer.echo(
            " | ".join(
                (
                    security.secid,
                    security.shortname or "",
                    security.secname or "",
                    security.boardid or "",
                    security.faceunit or "",
                    security.currencyid or "",
                )
            )
        )


@currency_app.command("candles")
def currency_candles(
    symbol: Annotated[str, typer.Option("--symbol", help="Concrete currency SECID")],
    from_date: Annotated[str, typer.Option("--from-date", help="Start date in YYYY-MM-DD")],
    till_date: Annotated[str, typer.Option("--till-date", help="End date in YYYY-MM-DD")],
    board: Annotated[
        str | None,
        typer.Option("--board", help="Currency BOARDID, for example CETS; discovered if omitted"),
    ] = None,
    timeframe: Annotated[str, typer.Option("--timeframe")] = DEFAULT_TIMEFRAME,
    save_raw: Annotated[bool, typer.Option("--save-raw")] = False,
    save_normalized: Annotated[bool, typer.Option("--save-normalized")] = False,
    data_root: Annotated[Path, typer.Option("--data-root")] = Path("data"),
    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
) -> None:
    """Download candles for one concrete MOEX currency instrument."""

    configure_logging(verbose)
    try:
        result = download_currency_candles(
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
