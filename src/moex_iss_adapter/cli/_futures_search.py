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
    print_metadata_snapshot_result,
)
from moex_iss_adapter.constants import (
    DEFAULT_FUTURES_ENGINE,
    DEFAULT_FUTURES_MARKET,
)
from moex_iss_adapter.downloads.futures import (
    search_saved_futures_metadata,
)
from moex_iss_adapter.exceptions import MoexIssAdapterError
from moex_iss_adapter.futures_history import contract_is_expired


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
    secid_prefix: Annotated[
        str | None,
        typer.Option("--secid-prefix", help="Keep SECIDs starting with this prefix"),
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
    include_expired: Annotated[
        bool,
        typer.Option("--include-expired", help="Search global ISS securities for expired futures"),
    ] = False,
    limit: Annotated[int, typer.Option("--limit", min=1, help="Maximum rows to print")] = 25,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
) -> None:
    """Search available MOEX futures contracts."""

    configure_logging(verbose)
    try:
        if include_expired:
            results = _public_cli_module().search_historical_futures_contracts(
                query=query or secid or asset_code or secid_prefix or "",
                secid_prefix=secid_prefix,
                asset_code=asset_code,
            )
            if secid:
                results = [
                    contract
                    for contract in results
                    if secid.casefold() in contract.secid.casefold()
                ]
        else:
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
                else _public_cli_module().search_futures_securities(
                    query=query,
                    secid=secid,
                    asset_code=asset_code,
                    short_name=short_name,
                    security_name=security_name,
                    engine=DEFAULT_FUTURES_ENGINE,
                    market=DEFAULT_FUTURES_MARKET,
                )
            )
            if secid_prefix:
                results = [
                    security
                    for security in results
                    if security.secid.upper().startswith(secid_prefix.upper())
                ]
    except MoexIssAdapterError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if not results:
        typer.echo("No futures securities matched the search.")
        return

    if include_expired:
        typer.echo(
            "SECID | BOARD | SHORTNAME | SECNAME | ASSETCODE | EXPIRATION_DATE | "
            "LAST_TRADE_DATE | IS_EXPIRED | SOURCE_ENDPOINT"
        )
        for contract in results[:limit]:
            typer.echo(
                " | ".join(
                    (
                        contract.secid,
                        contract.board,
                        contract.shortname or "",
                        contract.secname or "",
                        contract.assetcode or "",
                        str(contract.expiration_date or ""),
                        str(contract.last_trade_date or ""),
                        str(contract_is_expired(contract)),
                        contract.source_endpoint or "",
                    )
                )
            )
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
        result = _public_cli_module().save_futures_metadata_snapshot(
            save_raw=save_raw,
            save_normalized=save_normalized,
            data_root=data_root,
            overwrite=overwrite,
        )
    except MoexIssAdapterError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    print_metadata_snapshot_result(result)


def _public_cli_module():
    from moex_iss_adapter.cli import futures

    return futures
