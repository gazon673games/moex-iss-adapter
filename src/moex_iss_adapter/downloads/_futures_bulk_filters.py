"""Bulk futures metadata selection and candle preparation workflows."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import Any

from moex_iss_adapter.exceptions import MoexIssAdapterError
from moex_iss_adapter.models import (
    FuturesBulkSkip,
    FuturesChainContract,
    FuturesContractDateRange,
)

FUTURES_BULK_QUERY_FIELDS = ("secid", "shortname", "secname", "assetcode")


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_date(value: Any) -> date | None:
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


def _contains(value: Any, needle: str) -> bool:
    return needle.casefold() in str(value or "").casefold()


def _casefold_set(values: Iterable[str] | None) -> set[str]:
    return {value.casefold() for value in values or () if value.strip()}


def _parse_user_date(value: str, option_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        msg = f"{option_name} must be an ISO date in YYYY-MM-DD format"
        raise MoexIssAdapterError(msg) from exc


def _matches_filters(
    row: Mapping[str, Any],
    *,
    query: str | None,
    asset_code: str | None,
    secid_prefix: str | None,
    include_secids: set[str],
    exclude_secids: set[str],
    board: str | None,
) -> bool:
    secid = _optional_str(row.get("secid"))
    if include_secids and (secid is None or secid.casefold() not in include_secids):
        return False
    if exclude_secids and secid is not None and secid.casefold() in exclude_secids:
        return False
    if query and not any(_contains(row.get(field), query) for field in FUTURES_BULK_QUERY_FIELDS):
        return False
    if asset_code and not _contains(row.get("assetcode"), asset_code):
        return False
    if secid_prefix and (secid is None or not secid.casefold().startswith(secid_prefix.casefold())):
        return False
    if board:
        row_board = _optional_str(row.get("board"))
        if row_board is None or row_board.casefold() != board.casefold():
            return False
    return True


def _contract_from_row(row: Mapping[str, Any]) -> FuturesChainContract | FuturesBulkSkip:
    secid = _optional_str(row.get("secid"))
    board = _optional_str(row.get("board"))
    if not secid:
        return FuturesBulkSkip(board=board, reason="missing_secid", metadata_found=False)
    if not board:
        return FuturesBulkSkip(secid=secid, reason="missing_board", metadata_found=True)
    return FuturesChainContract(
        secid=secid,
        board=board,
        shortname=_optional_str(row.get("shortname")),
        secname=_optional_str(row.get("secname")),
        assetcode=_optional_str(row.get("assetcode")),
        last_trade_date=_optional_date(row.get("last_trade_date")),
        expiration_date=_optional_date(row.get("expiration_date")),
        metadata_found=True,
        source_endpoint="normalized_metadata_snapshot",
    )


def _contract_sort_key(contract: FuturesChainContract) -> tuple[bool, date, str]:
    sort_date = contract.expiration_date or contract.last_trade_date
    return sort_date is None, sort_date or date.max, contract.secid


def derive_contract_date_range(
    contract: FuturesChainContract,
    *,
    user_from_date: str,
    user_till_date: str,
    use_contract_date_ranges: bool,
) -> FuturesContractDateRange | FuturesBulkSkip:
    """Derive the MOEX candle request range for one selected futures contract."""

    from_date = _parse_user_date(user_from_date, "--from-date")
    _parse_user_date(user_till_date, "--till-date")
    if not use_contract_date_ranges:
        return FuturesContractDateRange(
            secid=contract.secid,
            board=contract.board,
            from_date=user_from_date,
            till_date=user_till_date,
        )

    metadata_end_date = contract.expiration_date or contract.last_trade_date
    if metadata_end_date is not None and metadata_end_date < from_date:
        return FuturesBulkSkip(
            secid=contract.secid,
            board=contract.board,
            reason="expired_before_from_date",
            metadata_found=contract.metadata_found,
        )

    till_date = metadata_end_date.isoformat() if metadata_end_date else user_till_date
    return FuturesContractDateRange(
        secid=contract.secid,
        board=contract.board,
        from_date=user_from_date,
        till_date=till_date,
    )
