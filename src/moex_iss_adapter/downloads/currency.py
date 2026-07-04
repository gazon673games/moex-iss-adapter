"""Currency discovery and candle download application services."""

from __future__ import annotations

from pathlib import Path

from moex_iss_adapter.client import MoexIssClient
from moex_iss_adapter.constants import (
    DEFAULT_CURRENCY_ENGINE,
    DEFAULT_CURRENCY_MARKET,
    DEFAULT_TIMEFRAME,
)
from moex_iss_adapter.currency import (
    find_currency_by_secid,
    parse_currency_securities,
    search_currency,
)
from moex_iss_adapter.downloads.candles import CandleDownloadRequest, run_candle_download
from moex_iss_adapter.exceptions import MoexIssAdapterError
from moex_iss_adapter.models import CurrencySecurity, DownloadResult, MoexIssConfig


def fetch_currency_securities(
    *,
    engine: str = DEFAULT_CURRENCY_ENGINE,
    market: str = DEFAULT_CURRENCY_MARKET,
    config: MoexIssConfig | None = None,
    client: MoexIssClient | None = None,
) -> list[CurrencySecurity]:
    """Fetch and parse available MOEX currency securities metadata."""

    effective_config = config or MoexIssConfig()
    owns_client = client is None
    effective_client = client or MoexIssClient(effective_config)
    try:
        response = effective_client.get_market_securities(engine, market)
    finally:
        if owns_client:
            effective_client.close()
    return parse_currency_securities(response)


def search_currency_securities(
    *,
    query: str | None = None,
    secid: str | None = None,
    short_name: str | None = None,
    security_name: str | None = None,
    face_unit: str | None = None,
    currency_id: str | None = None,
    engine: str = DEFAULT_CURRENCY_ENGINE,
    market: str = DEFAULT_CURRENCY_MARKET,
    config: MoexIssConfig | None = None,
    client: MoexIssClient | None = None,
) -> list[CurrencySecurity]:
    """Fetch currency securities and filter them with adapter-side search."""

    securities = fetch_currency_securities(
        engine=engine,
        market=market,
        config=config,
        client=client,
    )
    return search_currency(
        securities,
        query=query,
        secid=secid,
        short_name=short_name,
        security_name=security_name,
        face_unit=face_unit,
        currency_id=currency_id,
    )


def _discover_currency_board(
    *,
    symbol: str,
    engine: str,
    market: str,
    config: MoexIssConfig,
    client: MoexIssClient,
) -> str:
    # Для currency/selt доску берем из текущих ISS-метаданных инструмента:
    # это не зашивает CETS как вечное предположение.
    securities = fetch_currency_securities(
        engine=engine,
        market=market,
        config=config,
        client=client,
    )
    security = find_currency_by_secid(securities, symbol)
    if security and security.boardid:
        return security.boardid
    msg = (
        f"Could not discover board for currency instrument {symbol!r}. "
        "Run `moex-iss currency search --query <text>` and pass the discovered BOARDID "
        "with `--board`."
    )
    raise MoexIssAdapterError(msg)


def download_currency_candles(
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
    """Download candles for one concrete MOEX currency instrument."""

    effective_config = config or MoexIssConfig()
    owns_client = client is None
    effective_client = client or MoexIssClient(effective_config)
    try:
        resolved_board = board or _discover_currency_board(
            symbol=symbol,
            engine=DEFAULT_CURRENCY_ENGINE,
            market=DEFAULT_CURRENCY_MARKET,
            config=effective_config,
            client=effective_client,
        )
        request = CandleDownloadRequest(
            symbol=symbol,
            engine=DEFAULT_CURRENCY_ENGINE,
            market=DEFAULT_CURRENCY_MARKET,
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
