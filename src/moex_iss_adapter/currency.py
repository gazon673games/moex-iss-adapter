"""MOEX currency discovery helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from moex_iss_adapter.constants import DEFAULT_CURRENCY_ENGINE, DEFAULT_CURRENCY_MARKET
from moex_iss_adapter.exceptions import MoexResponseFormatError
from moex_iss_adapter.models import CurrencySecurity
from moex_iss_adapter.normalizers import parse_moex_table

CURRENCY_SEARCH_FIELDS = (
    "secid",
    "shortname",
    "secname",
    "latname",
    "faceunit",
    "currencyid",
)


# Валютные SECID на MOEX не всегда совпадают с интуитивными названиями пар,
# поэтому сначала ищем инструмент по метаданным, а затем скачиваем свечи по SECID.
def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_currency_securities(response: Mapping[str, Any]) -> list[CurrencySecurity]:
    """Parse MOEX currency securities metadata from a table-style ISS response."""

    rows = parse_moex_table(response, "securities")
    securities: list[CurrencySecurity] = []
    for row in rows:
        secid = row.get("secid")
        if not secid:
            msg = "MOEX currency securities row is missing SECID"
            raise MoexResponseFormatError(msg)
        securities.append(
            CurrencySecurity(
                secid=str(secid),
                boardid=_optional_str(row.get("boardid")),
                shortname=_optional_str(row.get("shortname")),
                secname=_optional_str(row.get("secname")),
                faceunit=_optional_str(row.get("faceunit")),
                currencyid=_optional_str(row.get("currencyid")),
                latname=_optional_str(row.get("latname")),
                marketcode=_optional_str(row.get("marketcode")),
                lotsize=_optional_float(row.get("lotsize")),
                settledate=_optional_str(row.get("settledate")),
            )
        )
    return securities


def search_currency(
    securities: Iterable[CurrencySecurity],
    *,
    query: str | None = None,
    secid: str | None = None,
    short_name: str | None = None,
    security_name: str | None = None,
    face_unit: str | None = None,
    currency_id: str | None = None,
) -> list[CurrencySecurity]:
    """Filter currency metadata by common search fields."""

    result = list(securities)
    if query:
        query_text = query.casefold()
        result = [
            security
            for security in result
            if any(
                query_text in str(getattr(security, field) or "").casefold()
                for field in CURRENCY_SEARCH_FIELDS
            )
        ]
    filters = (
        ("secid", secid),
        ("shortname", short_name),
        ("secname", security_name),
        ("faceunit", face_unit),
        ("currencyid", currency_id),
    )
    for field, value in filters:
        if value:
            needle = value.casefold()
            result = [
                security
                for security in result
                if needle in str(getattr(security, field) or "").casefold()
            ]
    return result


def find_currency_by_secid(
    securities: Iterable[CurrencySecurity],
    secid: str,
) -> CurrencySecurity | None:
    """Find one currency metadata row by exact SECID."""

    secid_text = secid.casefold()
    for security in securities:
        if security.secid.casefold() == secid_text:
            return security
    return None


def is_cny_or_usd_related_currency(security: CurrencySecurity | None) -> bool:
    """Return True when a currency instrument looks CNY/RUB or USD/RUB related."""

    if security is None:
        return False

    text = " ".join(
        str(value or "")
        for value in (
            security.secid,
            security.shortname,
            security.secname,
            security.latname,
            security.faceunit,
            security.currencyid,
        )
    ).casefold()
    return any(term in text for term in ("cny", "usd"))


def currency_market_defaults() -> tuple[str, str]:
    """Return default MOEX currency engine and market."""

    return DEFAULT_CURRENCY_ENGINE, DEFAULT_CURRENCY_MARKET
