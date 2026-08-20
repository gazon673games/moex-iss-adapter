"""Futures CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from moex_iss_adapter.cli._futures_core import (
    futures_app,
)
from moex_iss_adapter.cli.common import (
    configure_logging,
    print_download_result,
)
from moex_iss_adapter.constants import (
    DEFAULT_TIMEFRAME,
)
from moex_iss_adapter.exceptions import MoexIssAdapterError


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
        result = _public_cli_module().download_futures_candles(
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


def _public_cli_module():
    from moex_iss_adapter.cli import futures

    return futures
