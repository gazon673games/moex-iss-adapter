"""Candle download application services."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from moex_iss_adapter.client import MoexIssClient
from moex_iss_adapter.constants import (
    DEFAULT_BOARD,
    DEFAULT_ENGINE,
    DEFAULT_MARKET,
    DEFAULT_TIMEFRAME,
)
from moex_iss_adapter.exceptions import MoexPaginationError
from moex_iss_adapter.models import DownloadResult, MoexIssConfig
from moex_iss_adapter.normalizers import count_candle_rows, normalize_candles
from moex_iss_adapter.quality import validate_candles
from moex_iss_adapter.storage import save_normalized_candles, save_raw_candles

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CandleDownloadRequest:
    """Parameters for one canonical candle download use case."""

    symbol: str
    engine: str
    market: str
    board: str
    request_board: str | None
    timeframe: str
    from_date: str
    till_date: str
    save_raw: bool
    save_normalized: bool
    data_root: Path | str
    overwrite: bool


def download_candle_pages(
    *,
    client: MoexIssClient,
    config: MoexIssConfig,
    request: CandleDownloadRequest,
) -> list[dict]:
    """Download all MOEX ISS candle pages for a prepared request."""

    raw_pages: list[dict] = []
    start = 0

    for page_number in range(config.max_pages):
        logger.info(
            "Downloading MOEX ISS candle page",
            extra={
                "symbol": request.symbol,
                "board": request.board,
                "request_board": request.request_board,
                "timeframe": request.timeframe,
                "from_date": request.from_date,
                "till_date": request.till_date,
                "start": start,
            },
        )
        response = client.get_candles_page(
            engine=request.engine,
            market=request.market,
            board=request.request_board,
            security=request.symbol,
            timeframe=request.timeframe,
            from_date=request.from_date,
            till_date=request.till_date,
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


def run_candle_download(
    *,
    client: MoexIssClient,
    config: MoexIssConfig,
    request: CandleDownloadRequest,
) -> DownloadResult:
    """Download, normalize, quality-check, and optionally store candles."""

    raw_pages = download_candle_pages(client=client, config=config, request=request)
    normalized = normalize_candles(
        raw_pages,
        engine=request.engine,
        market=request.market,
        board=request.board,
        symbol=request.symbol,
        timeframe=request.timeframe,
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
    if request.save_raw:
        raw_path = save_raw_candles(
            responses=raw_pages,
            data_root=request.data_root,
            engine=request.engine,
            market=request.market,
            board=request.board,
            symbol=request.symbol,
            timeframe=request.timeframe,
            from_date=request.from_date,
            till_date=request.till_date,
            overwrite=request.overwrite,
        )
        logger.info("Saved raw MOEX ISS responses", extra={"path": str(raw_path)})

    if request.save_normalized:
        normalized_path = save_normalized_candles(
            frame=normalized,
            data_root=request.data_root,
            engine=request.engine,
            market=request.market,
            board=request.board,
            symbol=request.symbol,
            timeframe=request.timeframe,
            overwrite=request.overwrite,
        )
        logger.info("Saved normalized MOEX ISS candles", extra={"path": str(normalized_path)})

    return DownloadResult(
        symbol=request.symbol,
        engine=request.engine,
        market=request.market,
        board=request.board,
        timeframe=request.timeframe,
        from_date=request.from_date,
        till_date=request.till_date,
        row_count=quality_report.row_count,
        min_ts=quality_report.min_ts,
        max_ts=quality_report.max_ts,
        raw_path=raw_path,
        normalized_path=normalized_path,
        quality_report=quality_report,
    )


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
    request = CandleDownloadRequest(
        symbol=symbol,
        engine=engine,
        market=market,
        board=board,
        request_board=board,
        timeframe=timeframe,
        from_date=from_date,
        till_date=till_date,
        save_raw=save_raw,
        save_normalized=save_normalized,
        data_root=data_root,
        overwrite=overwrite,
    )
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
        return run_candle_download(
            client=effective_client, config=effective_config, request=request
        )
    finally:
        if owns_client:
            effective_client.close()
