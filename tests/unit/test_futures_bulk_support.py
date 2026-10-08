from __future__ import annotations

from datetime import datetime

from moex_iss_adapter.exceptions import MoexIssAdapterError

SNAPSHOT_TS = datetime(2026, 7, 4, 12, 30, 45)


class FakeBulkFuturesClient:
    def __init__(
        self,
        securities_response: dict,
        pages_by_symbol: dict[str, list[dict]],
        details_by_symbol: dict[str, dict] | None = None,
    ) -> None:
        self.securities_response = securities_response
        self.pages_by_symbol = pages_by_symbol
        self.details_by_symbol = details_by_symbol or {}
        self.requested_symbols: list[str] = []

    def get_market_securities(self, engine: str, market: str) -> dict:
        assert engine == "futures"
        assert market == "forts"
        return self.securities_response

    def get_candles_page(self, **kwargs) -> dict:
        symbol = kwargs["security"]
        self.requested_symbols.append(symbol)
        pages = self.pages_by_symbol[symbol]
        if len(pages) == 1:
            return pages[0]
        return pages.pop(0)

    def get_security_details(self, security: str) -> dict:
        try:
            return self.details_by_symbol[security]
        except KeyError as exc:
            msg = f"No fixture details for {security}"
            raise MoexIssAdapterError(msg) from exc
