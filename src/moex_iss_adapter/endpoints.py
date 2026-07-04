"""Centralized MOEX ISS endpoint definitions and request builders."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from moex_iss_adapter.constants import DEFAULT_BASE_URL, TIMEFRAME_TO_MOEX_INTERVAL
from moex_iss_adapter.exceptions import MoexIssAdapterError

CANDLES_PATH_TEMPLATE = (
    "/engines/{engine}/markets/{market}/boards/{board}/securities/{security}/candles.json"
)
MARKET_CANDLES_PATH_TEMPLATE = (
    "/engines/{engine}/markets/{market}/securities/{security}/candles.json"
)
ENGINES_PATH = "/engines.json"
MARKETS_PATH_TEMPLATE = "/engines/{engine}/markets.json"
BOARDS_PATH_TEMPLATE = "/engines/{engine}/markets/{market}/boards.json"
MARKET_SECURITIES_PATH_TEMPLATE = "/engines/{engine}/markets/{market}/securities.json"
SECURITIES_COLUMNS_PATH_TEMPLATE = "/engines/{engine}/markets/{market}/securities/columns.json"
SECURITIES_PATH_TEMPLATE = "/engines/{engine}/markets/{market}/boards/{board}/securities.json"
GLOBAL_SECURITIES_SEARCH_PATH = "/securities.json"
GLOBAL_SECURITY_DETAILS_PATH_TEMPLATE = "/securities/{security}.json"


def _require_path_value(name: str, value: str) -> str:
    if not value or not value.strip():
        msg = f"Missing required MOEX ISS path parameter: {name}"
        raise MoexIssAdapterError(msg)
    return quote(value.strip(), safe="")


def clean_base_url(base_url: str = DEFAULT_BASE_URL) -> str:
    """Return a base URL without trailing slash."""

    if not base_url or not base_url.strip():
        msg = "MOEX ISS base_url must not be empty"
        raise MoexIssAdapterError(msg)
    return base_url.rstrip("/")


def build_full_url(path: str, base_url: str = DEFAULT_BASE_URL) -> str:
    """Build a full URL from the configured base URL and centralized path."""

    if not path.startswith("/"):
        path = f"/{path}"
    return f"{clean_base_url(base_url)}{path}"


def moex_interval_for_timeframe(timeframe: str) -> int:
    """Return the MOEX ISS candle interval value for a normalized timeframe."""

    try:
        return TIMEFRAME_TO_MOEX_INTERVAL[timeframe]
    except KeyError as exc:
        supported = ", ".join(sorted(TIMEFRAME_TO_MOEX_INTERVAL))
        msg = f"Unsupported timeframe {timeframe!r}; supported values: {supported}"
        raise MoexIssAdapterError(msg) from exc


def build_engines_path() -> str:
    return ENGINES_PATH


def build_markets_path(engine: str) -> str:
    return MARKETS_PATH_TEMPLATE.format(engine=_require_path_value("engine", engine))


def build_boards_path(engine: str, market: str) -> str:
    return BOARDS_PATH_TEMPLATE.format(
        engine=_require_path_value("engine", engine),
        market=_require_path_value("market", market),
    )


def build_market_securities_path(engine: str, market: str) -> str:
    return MARKET_SECURITIES_PATH_TEMPLATE.format(
        engine=_require_path_value("engine", engine),
        market=_require_path_value("market", market),
    )


def build_securities_columns_path(engine: str, market: str) -> str:
    return SECURITIES_COLUMNS_PATH_TEMPLATE.format(
        engine=_require_path_value("engine", engine),
        market=_require_path_value("market", market),
    )


def build_securities_path(engine: str, market: str, board: str) -> str:
    return SECURITIES_PATH_TEMPLATE.format(
        engine=_require_path_value("engine", engine),
        market=_require_path_value("market", market),
        board=_require_path_value("board", board),
    )


def build_global_securities_search_path() -> str:
    return GLOBAL_SECURITIES_SEARCH_PATH


def build_global_security_details_path(security: str) -> str:
    return GLOBAL_SECURITY_DETAILS_PATH_TEMPLATE.format(
        security=_require_path_value("security", security),
    )


def build_candles_path(engine: str, market: str, board: str, security: str) -> str:
    return CANDLES_PATH_TEMPLATE.format(
        engine=_require_path_value("engine", engine),
        market=_require_path_value("market", market),
        board=_require_path_value("board", board),
        security=_require_path_value("security", security),
    )


def build_market_candles_path(engine: str, market: str, security: str) -> str:
    return MARKET_CANDLES_PATH_TEMPLATE.format(
        engine=_require_path_value("engine", engine),
        market=_require_path_value("market", market),
        security=_require_path_value("security", security),
    )


def build_candles_params(
    *,
    from_date: str,
    till_date: str,
    interval: int,
    start: int,
) -> dict[str, Any]:
    if start < 0:
        msg = "MOEX ISS start must be greater than or equal to zero"
        raise MoexIssAdapterError(msg)
    return {
        "from": from_date,
        "till": till_date,
        "interval": interval,
        "start": start,
    }


def build_candles_request(
    *,
    engine: str,
    market: str,
    board: str | None,
    security: str,
    from_date: str,
    till_date: str,
    timeframe: str,
    start: int,
) -> tuple[str, dict[str, Any]]:
    """Build candles path and query params.

    When `board` is None, build the market-level candles endpoint.
    """

    path = (
        build_candles_path(engine, market, board, security)
        if board is not None
        else build_market_candles_path(engine, market, security)
    )
    params = build_candles_params(
        from_date=from_date,
        till_date=till_date,
        interval=moex_interval_for_timeframe(timeframe),
        start=start,
    )
    return path, params
