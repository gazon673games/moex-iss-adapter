"""Backward-compatible download facade."""

from __future__ import annotations

from moex_iss_adapter.downloads.candles import download_candles
from moex_iss_adapter.downloads.currency import (
    download_currency_candles,
    fetch_currency_securities,
    search_currency_securities,
)
from moex_iss_adapter.downloads.futures import (
    download_futures_candles,
    fetch_futures_securities,
    fetch_futures_securities_response,
    search_futures_securities,
    search_saved_futures_metadata,
)
from moex_iss_adapter.downloads.futures_metadata import save_futures_metadata_snapshot

__all__ = [
    "download_candles",
    "download_currency_candles",
    "download_futures_candles",
    "fetch_currency_securities",
    "fetch_futures_securities",
    "fetch_futures_securities_response",
    "save_futures_metadata_snapshot",
    "search_currency_securities",
    "search_futures_securities",
    "search_saved_futures_metadata",
]
