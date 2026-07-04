"""Futures discovery and candle download application services."""

from __future__ import annotations

from pathlib import Path

from moex_iss_adapter.client import MoexIssClient
from moex_iss_adapter.constants import (
    DEFAULT_FUTURES_ENGINE,
    DEFAULT_FUTURES_MARKET,
    DEFAULT_TIMEFRAME,
)
from moex_iss_adapter.downloads.candles import CandleDownloadRequest, run_candle_download
from moex_iss_adapter.exceptions import MoexIssAdapterError
from moex_iss_adapter.futures import (
    find_futures_by_secid,
    parse_futures_securities,
    search_futures,
)
from moex_iss_adapter.metadata import load_futures_metadata_snapshot, search_futures_metadata
from moex_iss_adapter.models import DownloadResult, FuturesSecurity, MoexIssConfig


def fetch_futures_securities_response(
    *,
    engine: str = DEFAULT_FUTURES_ENGINE,
    market: str = DEFAULT_FUTURES_MARKET,
    config: MoexIssConfig | None = None,
    client: MoexIssClient | None = None,
) -> dict:
    """Fetch the raw MOEX futures securities metadata response."""

    effective_config = config or MoexIssConfig()
    owns_client = client is None
    effective_client = client or MoexIssClient(effective_config)
    try:
        return effective_client.get_market_securities(engine, market)
    finally:
        if owns_client:
            effective_client.close()


def fetch_futures_securities(
    *,
    engine: str = DEFAULT_FUTURES_ENGINE,
    market: str = DEFAULT_FUTURES_MARKET,
    config: MoexIssConfig | None = None,
    client: MoexIssClient | None = None,
) -> list[FuturesSecurity]:
    """Fetch and parse available MOEX futures securities metadata."""

    response = fetch_futures_securities_response(
        engine=engine,
        market=market,
        config=config,
        client=client,
    )
    return parse_futures_securities(response)


def search_futures_securities(
    *,
    query: str | None = None,
    secid: str | None = None,
    asset_code: str | None = None,
    short_name: str | None = None,
    security_name: str | None = None,
    engine: str = DEFAULT_FUTURES_ENGINE,
    market: str = DEFAULT_FUTURES_MARKET,
    config: MoexIssConfig | None = None,
    client: MoexIssClient | None = None,
) -> list[FuturesSecurity]:
    """Fetch futures securities and filter them with adapter-side search."""

    securities = fetch_futures_securities(
        engine=engine,
        market=market,
        config=config,
        client=client,
    )
    return search_futures(
        securities,
        query=query,
        secid=secid,
        asset_code=asset_code,
        short_name=short_name,
        security_name=security_name,
    )


def search_saved_futures_metadata(
    *,
    metadata_path: Path | str,
    query: str | None = None,
    secid: str | None = None,
    asset_code: str | None = None,
    short_name: str | None = None,
    security_name: str | None = None,
) -> list[FuturesSecurity]:
    """Search a saved normalized metadata snapshot."""

    frame = load_futures_metadata_snapshot(metadata_path)
    filtered = search_futures_metadata(
        frame,
        query=query,
        secid=secid,
        assetcode=asset_code,
        shortname=short_name,
        secname=security_name,
    )
    return [
        FuturesSecurity(
            secid=row["secid"],
            boardid=row["board"],
            shortname=row["shortname"],
            secname=row["secname"],
            assetcode=row["assetcode"],
            lasttradedate=str(row["last_trade_date"]) if row["last_trade_date"] else None,
            lastdeldate=str(row["expiration_date"]) if row["expiration_date"] else None,
            sectype=row["instrument_type"],
            lotvolume=row["lot_size"],
        )
        for row in filtered.iter_rows(named=True)
    ]


def _discover_futures_board(
    *,
    symbol: str,
    engine: str,
    market: str,
    config: MoexIssConfig,
    client: MoexIssClient,
) -> str:
    securities = fetch_futures_securities(
        engine=engine,
        market=market,
        config=config,
        client=client,
    )
    security = find_futures_by_secid(securities, symbol)
    if security and security.boardid:
        return security.boardid
    msg = (
        f"Could not discover board for futures contract {symbol!r}. "
        "Run `moex-iss futures search --query <text>` and pass the discovered BOARDID "
        "with `--board`."
    )
    raise MoexIssAdapterError(msg)


def download_futures_candles(
    *,
    symbol: str,
    from_date: str,
    till_date: str,
    board: str | None = None,
    timeframe: str = DEFAULT_TIMEFRAME,
    save_raw: bool = False,
    save_normalized: bool = False,
    data_root: Path | str = "data",
    overwrite: bool = False,
    config: MoexIssConfig | None = None,
    client: MoexIssClient | None = None,
) -> DownloadResult:
    """Download candles for one concrete MOEX futures contract."""

    effective_config = config or MoexIssConfig()
    owns_client = client is None
    effective_client = client or MoexIssClient(effective_config)
    try:
        resolved_board = board or _discover_futures_board(
            symbol=symbol,
            engine=DEFAULT_FUTURES_ENGINE,
            market=DEFAULT_FUTURES_MARKET,
            config=effective_config,
            client=effective_client,
        )
        request = CandleDownloadRequest(
            symbol=symbol,
            engine=DEFAULT_FUTURES_ENGINE,
            market=DEFAULT_FUTURES_MARKET,
            board=resolved_board,
            request_board=board,
            timeframe=timeframe,
            from_date=from_date,
            till_date=till_date,
            save_raw=save_raw,
            save_normalized=save_normalized,
            data_root=data_root,
            overwrite=overwrite,
        )
        return run_candle_download(
            client=effective_client, config=effective_config, request=request
        )
    finally:
        if owns_client:
            effective_client.close()
