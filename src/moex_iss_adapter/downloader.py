"""High-level candle download orchestration."""

from __future__ import annotations

import logging
from pathlib import Path

from moex_iss_adapter.client import MoexIssClient
from moex_iss_adapter.constants import (
    DEFAULT_BOARD,
    DEFAULT_CURRENCY_ENGINE,
    DEFAULT_CURRENCY_MARKET,
    DEFAULT_ENGINE,
    DEFAULT_FUTURES_ENGINE,
    DEFAULT_FUTURES_MARKET,
    DEFAULT_MARKET,
    DEFAULT_TIMEFRAME,
)
from moex_iss_adapter.currency import (
    find_currency_by_secid,
    parse_currency_securities,
    search_currency,
)
from moex_iss_adapter.exceptions import MoexIssAdapterError, MoexPaginationError
from moex_iss_adapter.futures import (
    find_futures_by_secid,
    parse_futures_securities,
    search_futures,
)
from moex_iss_adapter.metadata import (
    current_snapshot_ts,
    load_futures_metadata_snapshot,
    normalize_futures_metadata,
    search_futures_metadata,
)
from moex_iss_adapter.models import (
    CurrencySecurity,
    DownloadResult,
    FuturesSecurity,
    MetadataSnapshotResult,
    MoexIssConfig,
)
from moex_iss_adapter.normalizers import count_candle_rows, normalize_candles
from moex_iss_adapter.quality import validate_candles, validate_futures_metadata
from moex_iss_adapter.storage import (
    save_normalized_candles,
    save_normalized_futures_metadata,
    save_raw_candles,
    save_raw_futures_metadata,
)

logger = logging.getLogger(__name__)


def _download_candle_pages(
    *,
    client: MoexIssClient,
    config: MoexIssConfig,
    symbol: str,
    engine: str,
    market: str,
    board: str,
    request_board: str | None,
    timeframe: str,
    from_date: str,
    till_date: str,
) -> list[dict]:
    raw_pages: list[dict] = []
    start = 0

    for page_number in range(config.max_pages):
        logger.info(
            "Downloading MOEX ISS candle page",
            extra={
                "symbol": symbol,
                "board": board,
                "request_board": request_board,
                "timeframe": timeframe,
                "from_date": from_date,
                "till_date": till_date,
                "start": start,
            },
        )
        response = client.get_candles_page(
            engine=engine,
            market=market,
            board=request_board,
            security=symbol,
            timeframe=timeframe,
            from_date=from_date,
            till_date=till_date,
            start=start,
        )
        row_count = count_candle_rows(response)
        logger.info(
            "Downloaded MOEX ISS candle page",
            extra={"page_number": page_number, "start": start, "row_count": row_count},
        )
        raw_pages.append(response)
        if row_count == 0:
            return raw_pages
        start += row_count

    msg = f"MOEX ISS pagination reached max_pages={config.max_pages} without an empty page"
    raise MoexPaginationError(msg)


def download_candles(
    *,
    symbol: str,
    from_date: str,
    till_date: str,
    engine: str = DEFAULT_ENGINE,
    market: str = DEFAULT_MARKET,
    board: str = DEFAULT_BOARD,
    timeframe: str = DEFAULT_TIMEFRAME,
    save_raw: bool = False,
    save_normalized: bool = False,
    data_root: Path | str = "data",
    overwrite: bool = False,
    config: MoexIssConfig | None = None,
    client: MoexIssClient | None = None,
) -> DownloadResult:
    """Download, normalize, quality-check, and optionally store MOEX ISS candles."""

    effective_config = config or MoexIssConfig()
    logger.info(
        "Starting MOEX ISS candle download",
        extra={
            "symbol": symbol,
            "engine": engine,
            "market": market,
            "board": board,
            "timeframe": timeframe,
            "from_date": from_date,
            "till_date": till_date,
        },
    )

    owns_client = client is None
    effective_client = client or MoexIssClient(effective_config)
    try:
        raw_pages = _download_candle_pages(
            client=effective_client,
            config=effective_config,
            symbol=symbol,
            engine=engine,
            market=market,
            board=board,
            request_board=board,
            timeframe=timeframe,
            from_date=from_date,
            till_date=till_date,
        )
    finally:
        if owns_client:
            effective_client.close()

    normalized = normalize_candles(
        raw_pages,
        engine=engine,
        market=market,
        board=board,
        symbol=symbol,
        timeframe=timeframe,
    )
    quality_report = validate_candles(normalized)
    logger.info(
        "MOEX ISS candle quality check complete",
        extra={
            "passed": quality_report.passed,
            "row_count": quality_report.row_count,
            "duplicate_count": quality_report.duplicate_count,
        },
    )

    raw_path = None
    normalized_path = None

    if save_raw:
        raw_path = save_raw_candles(
            responses=raw_pages,
            data_root=data_root,
            engine=engine,
            market=market,
            board=board,
            symbol=symbol,
            timeframe=timeframe,
            from_date=from_date,
            till_date=till_date,
            overwrite=overwrite,
        )
        logger.info("Saved raw MOEX ISS responses", extra={"path": str(raw_path)})

    if save_normalized:
        normalized_path = save_normalized_candles(
            frame=normalized,
            data_root=data_root,
            engine=engine,
            market=market,
            board=board,
            symbol=symbol,
            timeframe=timeframe,
            overwrite=overwrite,
        )
        logger.info("Saved normalized MOEX ISS candles", extra={"path": str(normalized_path)})

    return DownloadResult(
        symbol=symbol,
        engine=engine,
        market=market,
        board=board,
        timeframe=timeframe,
        from_date=from_date,
        till_date=till_date,
        row_count=quality_report.row_count,
        min_ts=quality_report.min_ts,
        max_ts=quality_report.max_ts,
        raw_path=raw_path,
        normalized_path=normalized_path,
        quality_report=quality_report,
    )


def fetch_futures_securities(
    *,
    engine: str = DEFAULT_FUTURES_ENGINE,
    market: str = DEFAULT_FUTURES_MARKET,
    config: MoexIssConfig | None = None,
    client: MoexIssClient | None = None,
) -> list[FuturesSecurity]:
    """Fetch and parse available MOEX futures securities metadata."""

    effective_config = config or MoexIssConfig()
    owns_client = client is None
    effective_client = client or MoexIssClient(effective_config)
    try:
        response = effective_client.get_market_securities(engine, market)
    finally:
        if owns_client:
            effective_client.close()
    return parse_futures_securities(response)


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


def save_futures_metadata_snapshot(
    *,
    save_raw: bool = False,
    save_normalized: bool = False,
    data_root: Path | str = "data",
    overwrite: bool = False,
    snapshot_ts=None,
    engine: str = DEFAULT_FUTURES_ENGINE,
    market: str = DEFAULT_FUTURES_MARKET,
    config: MoexIssConfig | None = None,
    client: MoexIssClient | None = None,
) -> MetadataSnapshotResult:
    """Fetch, normalize, validate, and optionally save futures securities metadata."""

    effective_snapshot_ts = snapshot_ts or current_snapshot_ts()
    raw_response = fetch_futures_securities_response(
        engine=engine,
        market=market,
        config=config,
        client=client,
    )
    normalized = normalize_futures_metadata(
        raw_response,
        snapshot_ts=effective_snapshot_ts,
        engine=engine,
        market=market,
    )
    quality_report = validate_futures_metadata(normalized)

    raw_path = None
    normalized_path = None
    if save_raw:
        raw_path = save_raw_futures_metadata(
            response=raw_response,
            data_root=data_root,
            engine=engine,
            market=market,
            snapshot_ts=effective_snapshot_ts,
            overwrite=overwrite,
        )
    if save_normalized:
        normalized_path = save_normalized_futures_metadata(
            frame=normalized,
            data_root=data_root,
            engine=engine,
            market=market,
            snapshot_ts=effective_snapshot_ts,
            overwrite=overwrite,
        )

    return MetadataSnapshotResult(
        engine=engine,
        market=market,
        row_count=quality_report.row_count,
        snapshot_ts=effective_snapshot_ts,
        raw_path=raw_path,
        normalized_path=normalized_path,
        quality_report=quality_report,
    )


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


def _discover_currency_board(
    *,
    symbol: str,
    engine: str,
    market: str,
    config: MoexIssConfig,
    client: MoexIssClient,
) -> str:
    # Для currency/selt доску берем из текущих ISS-метаданных инструмента,
    # чтобы не зашивать CETS как постоянное предположение.
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
        request_board = board
        raw_pages = _download_candle_pages(
            client=effective_client,
            config=effective_config,
            symbol=symbol,
            engine=DEFAULT_FUTURES_ENGINE,
            market=DEFAULT_FUTURES_MARKET,
            board=resolved_board,
            request_board=request_board,
            timeframe=timeframe,
            from_date=from_date,
            till_date=till_date,
        )
    finally:
        if owns_client:
            effective_client.close()

    normalized = normalize_candles(
        raw_pages,
        engine=DEFAULT_FUTURES_ENGINE,
        market=DEFAULT_FUTURES_MARKET,
        board=resolved_board,
        symbol=symbol,
        timeframe=timeframe,
    )
    quality_report = validate_candles(normalized)

    raw_path = None
    normalized_path = None
    if save_raw:
        raw_path = save_raw_candles(
            responses=raw_pages,
            data_root=data_root,
            engine=DEFAULT_FUTURES_ENGINE,
            market=DEFAULT_FUTURES_MARKET,
            board=resolved_board,
            symbol=symbol,
            timeframe=timeframe,
            from_date=from_date,
            till_date=till_date,
            overwrite=overwrite,
        )
    if save_normalized:
        normalized_path = save_normalized_candles(
            frame=normalized,
            data_root=data_root,
            engine=DEFAULT_FUTURES_ENGINE,
            market=DEFAULT_FUTURES_MARKET,
            board=resolved_board,
            symbol=symbol,
            timeframe=timeframe,
            overwrite=overwrite,
        )

    return DownloadResult(
        symbol=symbol,
        engine=DEFAULT_FUTURES_ENGINE,
        market=DEFAULT_FUTURES_MARKET,
        board=resolved_board,
        timeframe=timeframe,
        from_date=from_date,
        till_date=till_date,
        row_count=quality_report.row_count,
        min_ts=quality_report.min_ts,
        max_ts=quality_report.max_ts,
        raw_path=raw_path,
        normalized_path=normalized_path,
        quality_report=quality_report,
    )


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
        request_board = board
        raw_pages = _download_candle_pages(
            client=effective_client,
            config=effective_config,
            symbol=symbol,
            engine=DEFAULT_CURRENCY_ENGINE,
            market=DEFAULT_CURRENCY_MARKET,
            board=resolved_board,
            request_board=request_board,
            timeframe=timeframe,
            from_date=from_date,
            till_date=till_date,
        )
    finally:
        if owns_client:
            effective_client.close()

    normalized = normalize_candles(
        raw_pages,
        engine=DEFAULT_CURRENCY_ENGINE,
        market=DEFAULT_CURRENCY_MARKET,
        board=resolved_board,
        symbol=symbol,
        timeframe=timeframe,
    )
    quality_report = validate_candles(normalized)

    raw_path = None
    normalized_path = None
    if save_raw:
        raw_path = save_raw_candles(
            responses=raw_pages,
            data_root=data_root,
            engine=DEFAULT_CURRENCY_ENGINE,
            market=DEFAULT_CURRENCY_MARKET,
            board=resolved_board,
            symbol=symbol,
            timeframe=timeframe,
            from_date=from_date,
            till_date=till_date,
            overwrite=overwrite,
        )
    if save_normalized:
        normalized_path = save_normalized_candles(
            frame=normalized,
            data_root=data_root,
            engine=DEFAULT_CURRENCY_ENGINE,
            market=DEFAULT_CURRENCY_MARKET,
            board=resolved_board,
            symbol=symbol,
            timeframe=timeframe,
            overwrite=overwrite,
        )

    return DownloadResult(
        symbol=symbol,
        engine=DEFAULT_CURRENCY_ENGINE,
        market=DEFAULT_CURRENCY_MARKET,
        board=resolved_board,
        timeframe=timeframe,
        from_date=from_date,
        till_date=till_date,
        row_count=quality_report.row_count,
        min_ts=quality_report.min_ts,
        max_ts=quality_report.max_ts,
        raw_path=raw_path,
        normalized_path=normalized_path,
        quality_report=quality_report,
    )
