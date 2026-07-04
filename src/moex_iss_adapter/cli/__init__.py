"""Typer CLI composition root for the MOEX ISS adapter."""

from __future__ import annotations

import typer

from . import candles as candle_commands
from . import currency as currency_commands
from . import futures as futures_commands
from . import metadata as metadata_commands

app = typer.Typer(help="MOEX ISS OHLCV adapter commands.")
app.command()(candle_commands.candles)
app.command()(candle_commands.quality)
app.add_typer(futures_commands.futures_app, name="futures")
app.add_typer(currency_commands.currency_app, name="currency")
app.add_typer(metadata_commands.metadata_app, name="metadata")


@app.callback()
def main() -> None:
    """Run MOEX ISS adapter commands."""
