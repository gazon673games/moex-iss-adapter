"""Low-level HTTP client for MOEX ISS."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from moex_iss_adapter.endpoints import (
    build_boards_path,
    build_candles_request,
    build_engines_path,
    build_global_securities_search_path,
    build_global_security_details_path,
    build_market_securities_path,
    build_markets_path,
    build_securities_columns_path,
    build_securities_path,
)
from moex_iss_adapter.exceptions import MoexHttpError, MoexResponseFormatError
from moex_iss_adapter.models import MoexIssConfig

logger = logging.getLogger(__name__)

TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}


class MoexIssClient:
    """Small bounded-retry HTTP client for MOEX ISS JSON endpoints."""

    def __init__(
        self,
        config: MoexIssConfig | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.config = config or MoexIssConfig()
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=self.config.base_url,
            timeout=self.config.timeout_seconds,
            headers={"User-Agent": self.config.user_agent},
            follow_redirects=True,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> MoexIssClient:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET a JSON endpoint and wrap HTTP/format failures in adapter exceptions."""

        last_error: Exception | None = None
        attempts = self.config.max_retries + 1

        for attempt in range(attempts):
            try:
                response = self._client.get(path, params=params)
                if response.status_code in TRANSIENT_STATUS_CODES:
                    response.raise_for_status()
                if response.is_error:
                    msg = f"MOEX ISS HTTP error {response.status_code} for {response.request.url}"
                    raise MoexHttpError(msg)

                payload = response.json()
                if not isinstance(payload, dict):
                    msg = "MOEX ISS JSON response must be an object"
                    raise MoexResponseFormatError(msg)
                return payload
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code not in TRANSIENT_STATUS_CODES:
                    msg = f"MOEX ISS HTTP error {exc.response.status_code} for {exc.request.url}"
                    raise MoexHttpError(msg) from exc
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as exc:
                last_error = exc
            except ValueError as exc:
                msg = "MOEX ISS response was not valid JSON"
                raise MoexResponseFormatError(msg) from exc

            if attempt < attempts - 1:
                sleep_seconds = min(0.25 * (2**attempt), 2.0)
                logger.debug(
                    "Retrying MOEX ISS request",
                    extra={"path": path, "attempt": attempt + 1, "sleep": sleep_seconds},
                )
                time.sleep(sleep_seconds)

        msg = f"MOEX ISS request failed after {attempts} attempts for {path}"
        raise MoexHttpError(msg) from last_error

    def get_engines(self) -> dict[str, Any]:
        return self.get_json(build_engines_path())

    def get_markets(self, engine: str) -> dict[str, Any]:
        return self.get_json(build_markets_path(engine))

    def get_boards(self, engine: str, market: str) -> dict[str, Any]:
        return self.get_json(build_boards_path(engine, market))

    def get_market_securities(self, engine: str, market: str) -> dict[str, Any]:
        return self.get_json(build_market_securities_path(engine, market))

    def get_securities_columns(self, engine: str, market: str) -> dict[str, Any]:
        return self.get_json(build_securities_columns_path(engine, market))

    def get_securities(self, engine: str, market: str, board: str) -> dict[str, Any]:
        return self.get_json(build_securities_path(engine, market, board))

    def search_global_securities(self, query: str, start: int = 0) -> dict[str, Any]:
        return self.get_json(
            build_global_securities_search_path(),
            params={
                "iss.only": "securities",
                "q": query,
                "start": start,
            },
        )

    def get_security_details(self, security: str) -> dict[str, Any]:
        return self.get_json(build_global_security_details_path(security))

    def get_candles_page(
        self,
        *,
        engine: str,
        market: str,
        board: str | None,
        security: str,
        timeframe: str,
        from_date: str,
        till_date: str,
        start: int,
    ) -> dict[str, Any]:
        path, params = build_candles_request(
            engine=engine,
            market=market,
            board=board,
            security=security,
            timeframe=timeframe,
            from_date=from_date,
            till_date=till_date,
            start=start,
        )
        return self.get_json(path, params=params)
