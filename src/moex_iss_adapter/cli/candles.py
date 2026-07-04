"""Root candle and quality CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import polars as pl
import typer

from moex_iss_adapter.cli.common import (
    configure_logging,
    print_candle_quality_report,
    print_download_result,
)
from moex_iss_adapter.constants import (
    DEFAULT_BOARD,
    DEFAULT_ENGINE,
    DEFAULT_MARKET,
    DEFAULT_TIMEFRAME,
)
from moex_iss_adapter.downloads.candles import download_candles
from moex_iss_adapter.exceptions import MoexIssAdapterError
from moex_iss_adapter.quality import validate_candles


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

    configure_logging(verbose)
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

    print_download_result(result)


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

    print_candle_quality_report(parquet_path, report)
