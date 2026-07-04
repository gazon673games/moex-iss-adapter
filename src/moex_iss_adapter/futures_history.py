"""Discovery helpers for historical MOEX FORTS futures contracts."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from moex_iss_adapter.constants import DEFAULT_FUTURES_ENGINE, DEFAULT_FUTURES_MARKET
from moex_iss_adapter.models import FuturesChainContract
from moex_iss_adapter.normalizers import parse_moex_table

SECURITIES_SEARCH_ENDPOINT = "/securities.json"
SECURITY_DETAILS_ENDPOINT_TEMPLATE = "/securities/{secid}.json"
FUTURES_FORTS_GROUP = "futures_forts"
FUTURES_TYPE = "futures"


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _norm(value: Any) -> str:
    return str(value or "").strip().casefold()


def _description_map(response: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for row in parse_moex_table(response, "description"):
        name = _text(row.get("name"))
        if name:
            result[name.upper()] = row.get("value")
    return result


def _primary_futures_board(response: Mapping[str, Any]) -> dict[str, Any] | None:
    boards = [
        row
        for row in parse_moex_table(response, "boards")
        if _norm(row.get("engine")) == DEFAULT_FUTURES_ENGINE
        and _norm(row.get("market")) == DEFAULT_FUTURES_MARKET
    ]
    if not boards:
        return None
    primary = [row for row in boards if row.get("is_primary") in (1, True, "1")]
    return (primary or boards)[0]


def search_response_futures_secids(
    response: Mapping[str, Any],
    *,
    secid_prefix: str | None = None,
) -> list[str]:
    """Extract FORTS futures SECIDs from a global securities search response."""

    secids: list[str] = []
    seen: set[str] = set()
    for row in parse_moex_table(response, "securities"):
        if _norm(row.get("group")) != FUTURES_FORTS_GROUP:
            continue
        if _norm(row.get("type")) != FUTURES_TYPE:
            continue
        secid = _text(row.get("secid"))
        if not secid:
            continue
        if secid_prefix and not secid.upper().startswith(secid_prefix.upper()):
            continue
        if secid.upper() in seen:
            continue
        seen.add(secid.upper())
        secids.append(secid)
    return secids


def contract_from_security_details(
    secid: str,
    response: Mapping[str, Any],
    *,
    source_endpoint: str | None = None,
    metadata_found: bool = True,
) -> FuturesChainContract | None:
    """Build a contract descriptor from `/securities/<SECID>.json` response."""

    description = _description_map(response)
    board = _primary_futures_board(response)
    if board is None:
        return None

    boardid = _text(board.get("boardid"))
    if not boardid:
        return None

    last_trade_date = _date(description.get("LSTTRADE") or board.get("listed_till"))
    expiration_date = _date(description.get("LSTDELDATE") or board.get("history_till"))
    return FuturesChainContract(
        secid=secid,
        board=boardid,
        shortname=_text(description.get("SHORTNAME")),
        secname=_text(
            description.get("SECNAME") or description.get("NAME") or description.get("CONTRACTNAME")
        ),
        assetcode=_text(description.get("ASSETCODE")),
        last_trade_date=last_trade_date,
        expiration_date=expiration_date or last_trade_date,
        metadata_found=metadata_found,
        source_endpoint=source_endpoint or SECURITY_DETAILS_ENDPOINT_TEMPLATE.format(secid=secid),
    )


def contract_is_expired(contract: FuturesChainContract, today: date | None = None) -> bool:
    """Return whether a discovered futures contract is expired by metadata."""

    effective_today = today or date.today()
    end_date = contract.expiration_date or contract.last_trade_date
    return end_date is not None and end_date < effective_today
