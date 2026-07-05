"""Stable constants for the MOEX ISS adapter."""

from __future__ import annotations

from typing import Final

DEFAULT_BASE_URL: Final = "https://iss.moex.com/iss"
DEFAULT_ENGINE: Final = "stock"
DEFAULT_MARKET: Final = "shares"
DEFAULT_BOARD: Final = "TQBR"
DEFAULT_FUTURES_ENGINE: Final = "futures"
DEFAULT_FUTURES_MARKET: Final = "forts"
DEFAULT_FUTURES_BOARD: Final = "RFUD"
DEFAULT_CURRENCY_ENGINE: Final = "currency"
DEFAULT_CURRENCY_MARKET: Final = "selt"
DEFAULT_TIMEFRAME: Final = "1d"
DEFAULT_EXCHANGE: Final = "MOEX"
DEFAULT_SOURCE: Final = "moex"

CANONICAL_OHLCV_COLUMNS: Final[tuple[str, ...]] = (
    "source",
    "exchange",
    "engine",
    "market",
    "board",
    "symbol",
    "timeframe",
    "ts",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "value",
    "currency",
)

FUTURES_METADATA_COLUMNS: Final[tuple[str, ...]] = (
    "source",
    "exchange",
    "engine",
    "market",
    "board",
    "secid",
    "shortname",
    "secname",
    "assetcode",
    "instrument_type",
    "last_trade_date",
    "expiration_date",
    "currency",
    "lot_size",
    "raw_metadata",
    "snapshot_ts",
)

UNIQUE_KEY_COLUMNS: Final[tuple[str, ...]] = (
    "source",
    "exchange",
    "board",
    "symbol",
    "timeframe",
    "ts",
)

FUTURES_METADATA_UNIQUE_KEY_COLUMNS: Final[tuple[str, ...]] = ("secid", "board")

FORBIDDEN_NORMALIZED_TIMESTAMP_COLUMNS: Final[tuple[str, ...]] = (
    "begin",
    "date",
    "datetime",
    "timestamp",
    "time",
)

TIMEFRAME_TO_MOEX_INTERVAL: Final[dict[str, int]] = {
    "1m": 1,
    # MOEX ISS does not expose native 5-minute candles for FORTS in this workflow.
    # The adapter requests 1-minute candles and normalizes them into 5-minute bars.
    "5m": 1,
    "10m": 10,
    "1h": 60,
    "1d": 24,
    "1w": 7,
    "1mo": 31,
    "1q": 4,
}
