"""Metadata snapshot CLI commands."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from moex_iss_adapter.storage import list_metadata_snapshots

metadata_app = typer.Typer(help="Saved metadata snapshot commands.")


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
