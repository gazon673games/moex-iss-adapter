"""Sampling and candidate selection for MOEX ISS snapshot refreshes."""

from __future__ import annotations

from typing import Any

from moex_iss_adapter.currency import CurrencySecurity, is_cny_or_usd_related_currency
from moex_iss_adapter.futures import FuturesSecurity, is_cny_related_futures


def _sample_table(
    payload: dict[str, Any],
    table_name: str,
    rows: list[list[Any]],
) -> dict[str, Any]:
    table = payload[table_name]
    return {
        table_name: {
            "columns": table["columns"],
            "data": rows,
            "metadata": table.get("metadata", {}),
        }
    }


def _row_dict(columns: list[str], row: list[Any]) -> dict[str, Any]:
    return dict(zip([column.lower() for column in columns], row, strict=True))


def sample_futures_securities(payload: dict[str, Any], limit: int = 12) -> dict[str, Any]:
    table = payload["securities"]
    columns = table["columns"]
    rows = table["data"]
    cny_rows = []
    for row in rows:
        values = _row_dict(columns, row)
        text = " ".join(
            str(values.get(field, "")).casefold()
            for field in ("secid", "shortname", "secname", "assetcode", "latname")
        )
        if any(token in text for token in ("cny", "yuan", "rmb", "ucny")):
            cny_rows.append(row)
    if cny_rows:
        selected_rows = cny_rows[:limit]
    else:
        selected_rows = sorted(
            rows,
            key=lambda row: _row_dict(columns, row).get("prevopenposition") or 0,
            reverse=True,
        )[:limit]
    return _sample_table(payload, "securities", selected_rows)


def sample_currency_securities(payload: dict[str, Any], limit: int = 12) -> dict[str, Any]:
    table = payload["securities"]
    columns = table["columns"]
    rows = table["data"]
    cny_rows = []
    usd_rows = []
    for row in rows:
        values = _row_dict(columns, row)
        text = " ".join(
            str(values.get(field, "")).casefold()
            for field in ("secid", "shortname", "secname", "faceunit", "currencyid", "latname")
        )
        if "cny" in text:
            cny_rows.append(row)
        if "usd" in text:
            usd_rows.append(row)
    preferred_rows = cny_rows[: limit // 2]
    preferred_rows.extend(usd_rows[: limit - (limit // 2)])
    selected_rows = preferred_rows[:limit] if preferred_rows else rows[:limit]
    return _sample_table(payload, "securities", selected_rows)


def choose_futures_candidate(
    securities: list[FuturesSecurity],
) -> tuple[FuturesSecurity | None, str]:
    cny_candidates = [security for security in securities if is_cny_related_futures(security)]
    preferred = next((security for security in cny_candidates if security.secid == "CNYRUBF"), None)
    if preferred:
        return preferred, "selected CNY/RUB-related CNYRUBF contract"
    if cny_candidates:
        return (
            max(cny_candidates, key=lambda security: security.prevopenposition or 0),
            "selected liquid CNY/RUB-related futures contract",
        )
    if securities:
        return (
            max(securities, key=lambda security: security.prevopenposition or 0),
            "no CNY/RUB-related futures found; selected fallback liquid futures contract",
        )
    return None, "no futures securities returned"


def choose_currency_candidate(
    securities: list[CurrencySecurity],
) -> tuple[CurrencySecurity | None, str]:
    candidates = [security for security in securities if is_cny_or_usd_related_currency(security)]
    cny_preferred = next(
        (security for security in candidates if security.secid == "CNY000000TOD"),
        None,
    )
    if cny_preferred:
        return cny_preferred, "selected CNY/RUB-related CNY000000TOD instrument"
    usd_preferred = next(
        (security for security in candidates if security.secid == "USD000UTSTOM"),
        None,
    )
    if usd_preferred:
        return usd_preferred, "selected USD/RUB-related USD000UTSTOM instrument"
    if candidates:
        return candidates[0], "selected discovered CNY/USD-related currency instrument"
    if securities:
        return securities[0], "no CNY/USD-related currency found; selected fallback instrument"
    return None, "no currency securities returned"
