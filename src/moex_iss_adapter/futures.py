"""Futures discovery helpers for MOEX ISS."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from moex_iss_adapter.constants import DEFAULT_FUTURES_ENGINE, DEFAULT_FUTURES_MARKET
from moex_iss_adapter.exceptions import MoexResponseFormatError
from moex_iss_adapter.models import FuturesSecurity
from moex_iss_adapter.normalizers import parse_moex_table

FUTURES_SEARCH_FIELDS = ("secid", "assetcode", "shortname", "secname", "latname")


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_futures_securities(response: Mapping[str, Any]) -> list[FuturesSecurity]:
    """Parse MOEX futures securities metadata from a table-style ISS response."""

    rows = parse_moex_table(response, "securities")
    securities: list[FuturesSecurity] = []
    for row in rows:
        secid = row.get("secid")
        if not secid:
            msg = "MOEX futures securities row is missing SECID"
            raise MoexResponseFormatError(msg)
        securities.append(
            FuturesSecurity(
                secid=str(secid),
                boardid=_optional_str(row.get("boardid")),
                shortname=_optional_str(row.get("shortname")),
                secname=_optional_str(row.get("secname")),
                assetcode=_optional_str(row.get("assetcode")),
                latname=_optional_str(row.get("latname")),
                lasttradedate=_optional_str(row.get("lasttradedate")),
                lastdeldate=_optional_str(row.get("lastdeldate")),
                sectype=_optional_str(row.get("sectype")),
                lotvolume=_optional_float(row.get("lotvolume")),
                prevopenposition=_optional_float(row.get("prevopenposition")),
            )
        )
    return securities


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def search_futures(
    securities: Iterable[FuturesSecurity],
    *,
    query: str | None = None,
    secid: str | None = None,
    asset_code: str | None = None,
    short_name: str | None = None,
    security_name: str | None = None,
) -> list[FuturesSecurity]:
    """Filter futures metadata by query, asset code, short name, or security name."""

    result = list(securities)
    if query:
        query_text = query.casefold()
        result = [
            security
            for security in result
            if any(
                query_text in str(getattr(security, field) or "").casefold()
                for field in FUTURES_SEARCH_FIELDS
            )
        ]
    if secid:
        secid_text = secid.casefold()
        result = [
            security for security in result if secid_text in str(security.secid or "").casefold()
        ]
    if asset_code:
        asset_text = asset_code.casefold()
        result = [
            security
            for security in result
            if asset_text in str(security.assetcode or "").casefold()
        ]
    if short_name:
        short_text = short_name.casefold()
        result = [
            security
            for security in result
            if short_text in str(security.shortname or "").casefold()
        ]
    if security_name:
        name_text = security_name.casefold()
        result = [
            security for security in result if name_text in str(security.secname or "").casefold()
        ]
    return result


def find_futures_by_secid(
    securities: Iterable[FuturesSecurity],
    secid: str,
) -> FuturesSecurity | None:
    """Find one futures metadata row by exact SECID."""

    secid_text = secid.casefold()
    for security in securities:
        if security.secid.casefold() == secid_text:
            return security
    return None


def is_cny_related_futures(security: FuturesSecurity | None) -> bool:
    """Return True when a futures instrument looks CNY/RUB-related."""

    if security is None:
        return False

    text = " ".join(
        str(value or "")
        for value in (
            security.secid,
            security.shortname,
            security.secname,
            security.assetcode,
            security.latname,
        )
    ).casefold()
    return any(term in text for term in ("cny", "yuan", "rmb", "cnyrub", "ucny"))


def futures_market_defaults() -> tuple[str, str]:
    """Return default MOEX futures engine and market."""

    return DEFAULT_FUTURES_ENGINE, DEFAULT_FUTURES_MARKET
