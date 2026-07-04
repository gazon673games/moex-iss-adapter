"""Application services for historical MOEX futures discovery."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from moex_iss_adapter.client import MoexIssClient
from moex_iss_adapter.exceptions import MoexIssAdapterError
from moex_iss_adapter.futures_history import (
    SECURITY_DETAILS_ENDPOINT_TEMPLATE,
    contract_from_security_details,
    search_response_futures_secids,
)
from moex_iss_adapter.models import FuturesChainContract, MoexIssConfig

DEFAULT_HISTORY_SEARCH_MAX_PAGES = 25


def _norm(value: str) -> str:
    return value.strip().casefold()


def _casefold_set(values: Iterable[str] | None) -> set[str]:
    return {_norm(value) for value in values or () if value.strip()}


def _sort_key(contract: FuturesChainContract) -> tuple[date, str]:
    return contract.expiration_date or contract.last_trade_date or date.max, contract.secid


def fetch_futures_contract_details(
    *,
    secid: str,
    config: MoexIssConfig | None = None,
    client: MoexIssClient | None = None,
) -> FuturesChainContract | None:
    """Fetch one historical/current futures contract descriptor from global security details."""

    effective_config = config or MoexIssConfig()
    owns_client = client is None
    effective_client = client or MoexIssClient(effective_config)
    try:
        response = effective_client.get_security_details(secid)
        return contract_from_security_details(
            secid,
            response,
            source_endpoint=SECURITY_DETAILS_ENDPOINT_TEMPLATE.format(secid=secid),
        )
    finally:
        if owns_client:
            effective_client.close()


def search_historical_futures_contracts(
    *,
    query: str,
    secid_prefix: str | None = None,
    asset_code: str | None = None,
    exclude_secids: Iterable[str] | None = None,
    limit: int | None = None,
    max_pages: int = DEFAULT_HISTORY_SEARCH_MAX_PAGES,
    config: MoexIssConfig | None = None,
    client: MoexIssClient | None = None,
) -> list[FuturesChainContract]:
    """Search global ISS securities and hydrate matching FORTS futures details."""

    if not query.strip():
        msg = "Historical futures search requires a non-empty query"
        raise MoexIssAdapterError(msg)

    effective_config = config or MoexIssConfig()
    owns_client = client is None
    effective_client = client or MoexIssClient(effective_config)
    excluded = _casefold_set(exclude_secids)
    contracts: list[FuturesChainContract] = []
    seen: set[str] = set()
    start = 0
    try:
        for _page in range(max_pages):
            response = effective_client.search_global_securities(query, start=start)
            secids = search_response_futures_secids(response, secid_prefix=secid_prefix)
            rows = response.get("securities", {}).get("data", [])
            if not isinstance(rows, list) or not rows:
                break

            for secid in secids:
                key = _norm(secid)
                if key in seen or key in excluded:
                    continue
                details = fetch_futures_contract_details(
                    secid=secid,
                    config=effective_config,
                    client=effective_client,
                )
                if details is None:
                    continue
                if asset_code and _norm(details.assetcode or "") != _norm(asset_code):
                    continue
                seen.add(key)
                contracts.append(details)
                if limit is not None and len(contracts) >= limit:
                    return sorted(
                        contracts,
                        key=_sort_key,
                    )

            start += len(rows)

        return sorted(
            contracts,
            key=_sort_key,
        )
    finally:
        if owns_client:
            effective_client.close()
