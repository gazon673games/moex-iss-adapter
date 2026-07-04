"""Fetch small MOEX ISS snapshots for local documentation and fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from moex_iss_adapter.constants import (  # noqa: E402
    DEFAULT_BASE_URL,
    DEFAULT_CURRENCY_ENGINE,
    DEFAULT_CURRENCY_MARKET,
    DEFAULT_FUTURES_ENGINE,
    DEFAULT_FUTURES_MARKET,
    DEFAULT_TIMEFRAME,
)
from moex_iss_adapter.currency import (  # noqa: E402
    CurrencySecurity,
    is_cny_or_usd_related_currency,
    parse_currency_securities,
)
from moex_iss_adapter.endpoints import (  # noqa: E402
    build_boards_path,
    build_candles_request,
    build_engines_path,
    build_market_securities_path,
    build_markets_path,
    build_securities_columns_path,
)
from moex_iss_adapter.futures import (  # noqa: E402
    FuturesSecurity,
    is_cny_related_futures,
    parse_futures_securities,
)
from moex_iss_adapter.metadata import current_snapshot_ts, normalize_futures_metadata  # noqa: E402
from moex_iss_adapter.storage import (  # noqa: E402
    save_normalized_futures_metadata,
    save_raw_futures_metadata,
)

SNAPSHOT_DIR = ROOT / "docs" / "moex_iss" / "snapshots"
FIXTURE_DIR = ROOT / "tests" / "fixtures"


def _fetch_json(client: httpx.Client, path: str, params: dict[str, Any] | None = None) -> Any:
    response = client.get(path, params=params)
    response.raise_for_status()
    return response.json()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


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


def _sample_futures_securities(payload: dict[str, Any], limit: int = 12) -> dict[str, Any]:
    table = payload["securities"]
    columns = table["columns"]
    rows = table["data"]
    cny_rows = [
        row
        for row in rows
        if any(
            token in str(_row_dict(columns, row).get(field, "")).casefold()
            for field in ("secid", "shortname", "secname", "assetcode", "latname")
            for token in ("cny", "yuan", "rmb", "ucny")
        )
    ]
    if cny_rows:
        selected_rows = cny_rows[:limit]
    else:
        selected_rows = sorted(
            rows,
            key=lambda row: _row_dict(columns, row).get("prevopenposition") or 0,
            reverse=True,
        )[:limit]
    return _sample_table(payload, "securities", selected_rows)


def _sample_currency_securities(payload: dict[str, Any], limit: int = 12) -> dict[str, Any]:
    table = payload["securities"]
    columns = table["columns"]
    rows = table["data"]
    cny_rows = [
        row
        for row in rows
        if any(
            "cny" in str(_row_dict(columns, row).get(field, "")).casefold()
            for field in ("secid", "shortname", "secname", "faceunit", "currencyid", "latname")
        )
    ]
    usd_rows = [
        row
        for row in rows
        if any(
            "usd" in str(_row_dict(columns, row).get(field, "")).casefold()
            for field in ("secid", "shortname", "secname", "faceunit", "currencyid", "latname")
        )
    ]
    preferred_rows = [*cny_rows[: limit // 2], *usd_rows[: limit - (limit // 2)]]
    selected_rows = preferred_rows[:limit] if preferred_rows else rows[:limit]
    return _sample_table(payload, "securities", selected_rows)


def _choose_futures_candidate(
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


def _choose_currency_candidate(
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
        return securities[
            0
        ], "no CNY/USD-related currency found; selected fallback currency instrument"
    return None, "no currency securities returned"


def main() -> int:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    candle_path, candle_params = build_candles_request(
        engine="stock",
        market="shares",
        board="TQBR",
        security="SBER",
        from_date="2023-01-10",
        till_date="2023-01-20",
        timeframe=DEFAULT_TIMEFRAME,
        start=0,
    )

    requests: dict[str, tuple[str, dict[str, Any] | None]] = {
        "engines.json": (build_engines_path(), None),
        "markets_stock.json": (build_markets_path("stock"), None),
        "boards_stock_shares.json": (build_boards_path("stock", "shares"), None),
        "durations.json": ("/index.json", {"iss.only": "durations"}),
        "candles_sber_tqbr_1d_2023-01-10_2023-01-20.json": (candle_path, candle_params),
        "futures_forts_boards.json": (
            build_boards_path(DEFAULT_FUTURES_ENGINE, DEFAULT_FUTURES_MARKET),
            None,
        ),
        "futures_forts_securities_columns.json": (
            build_securities_columns_path(DEFAULT_FUTURES_ENGINE, DEFAULT_FUTURES_MARKET),
            None,
        ),
        "currency_selt_boards.json": (
            build_boards_path(DEFAULT_CURRENCY_ENGINE, DEFAULT_CURRENCY_MARKET),
            None,
        ),
        "currency_selt_securities_columns.json": (
            build_securities_columns_path(DEFAULT_CURRENCY_ENGINE, DEFAULT_CURRENCY_MARKET),
            None,
        ),
    }

    try:
        with httpx.Client(base_url=DEFAULT_BASE_URL, timeout=20.0, follow_redirects=True) as client:
            snapshots = {
                filename: _fetch_json(client, path, params)
                for filename, (path, params) in requests.items()
            }
            futures_securities = _fetch_json(
                client,
                build_market_securities_path(DEFAULT_FUTURES_ENGINE, DEFAULT_FUTURES_MARKET),
            )
            metadata_snapshot_ts = current_snapshot_ts()
            normalized_metadata = normalize_futures_metadata(
                futures_securities,
                snapshot_ts=metadata_snapshot_ts,
            )
            futures_sample = _sample_futures_securities(futures_securities)
            futures_candidates = parse_futures_securities(futures_securities)
            selected_futures, selection_note = _choose_futures_candidate(futures_candidates)
            snapshots["futures_forts_securities_sample.json"] = futures_sample

            raw_metadata_path = save_raw_futures_metadata(
                response=futures_securities,
                data_root=SNAPSHOT_DIR,
                engine=DEFAULT_FUTURES_ENGINE,
                market=DEFAULT_FUTURES_MARKET,
                snapshot_ts=metadata_snapshot_ts,
                overwrite=True,
            )
            normalized_metadata_path = save_normalized_futures_metadata(
                frame=normalized_metadata,
                data_root=SNAPSHOT_DIR,
                engine=DEFAULT_FUTURES_ENGINE,
                market=DEFAULT_FUTURES_MARKET,
                snapshot_ts=metadata_snapshot_ts,
                overwrite=True,
            )
            futures_metadata: dict[str, Any] = {
                "selection_note": selection_note,
                "metadata_snapshot_ts": metadata_snapshot_ts.isoformat(),
                "raw_metadata_path": str(raw_metadata_path.relative_to(ROOT)),
                "normalized_metadata_path": str(normalized_metadata_path.relative_to(ROOT)),
                "selected_security": selected_futures.model_dump()
                if selected_futures is not None
                else None,
            }
            if selected_futures is not None:
                futures_from = "2023-01-10" if selected_futures.secid == "CNYRUBF" else "2026-07-01"
                futures_till = "2023-01-20" if selected_futures.secid == "CNYRUBF" else "2026-07-03"
                futures_candle_path, futures_candle_params = build_candles_request(
                    engine=DEFAULT_FUTURES_ENGINE,
                    market=DEFAULT_FUTURES_MARKET,
                    board=None,
                    security=selected_futures.secid,
                    from_date=futures_from,
                    till_date=futures_till,
                    timeframe=DEFAULT_TIMEFRAME,
                    start=0,
                )
                futures_candles = _fetch_json(client, futures_candle_path, futures_candle_params)
                snapshots["futures_forts_candles_sample.json"] = futures_candles
                futures_metadata["candles"] = {
                    "from": futures_from,
                    "till": futures_till,
                    "path": futures_candle_path,
                    "params": futures_candle_params,
                }
            snapshots["futures_snapshot_metadata.json"] = futures_metadata

            currency_securities = _fetch_json(
                client,
                build_market_securities_path(DEFAULT_CURRENCY_ENGINE, DEFAULT_CURRENCY_MARKET),
            )
            currency_sample = _sample_currency_securities(currency_securities)
            currency_candidates = parse_currency_securities(currency_securities)
            selected_currency, currency_selection_note = _choose_currency_candidate(
                currency_candidates
            )
            snapshots["currency_selt_securities_sample.json"] = currency_sample

            currency_metadata: dict[str, Any] = {
                "selection_note": currency_selection_note,
                "selected_security": selected_currency.model_dump()
                if selected_currency is not None
                else None,
            }
            if selected_currency is not None:
                currency_candle_path, currency_candle_params = build_candles_request(
                    engine=DEFAULT_CURRENCY_ENGINE,
                    market=DEFAULT_CURRENCY_MARKET,
                    board=None,
                    security=selected_currency.secid,
                    from_date="2023-01-10",
                    till_date="2023-01-20",
                    timeframe=DEFAULT_TIMEFRAME,
                    start=0,
                )
                currency_candles = _fetch_json(client, currency_candle_path, currency_candle_params)
                snapshots["currency_selt_candles_sample.json"] = currency_candles
                currency_metadata["candles"] = {
                    "from": "2023-01-10",
                    "till": "2023-01-20",
                    "path": currency_candle_path,
                    "params": currency_candle_params,
                }
            snapshots["currency_snapshot_metadata.json"] = currency_metadata
    except httpx.HTTPError as exc:
        print(f"MOEX ISS snapshots were not refreshed: {exc}", file=sys.stderr)
        return 1

    for filename, payload in snapshots.items():
        _write_json(SNAPSHOT_DIR / filename, payload)

    _write_json(
        FIXTURE_DIR / "moex_candles_sber_tqbr_1d_sample.json",
        snapshots["candles_sber_tqbr_1d_2023-01-10_2023-01-20.json"],
    )
    _write_json(
        FIXTURE_DIR / "moex_futures_securities_sample.json",
        snapshots["futures_forts_securities_sample.json"],
    )
    _write_json(
        FIXTURE_DIR / "moex_futures_boards_sample.json",
        snapshots["futures_forts_boards.json"],
    )
    if "futures_forts_candles_sample.json" in snapshots:
        _write_json(
            FIXTURE_DIR / "moex_futures_candles_sample.json",
            snapshots["futures_forts_candles_sample.json"],
        )
    _write_json(
        FIXTURE_DIR / "moex_currency_securities_sample.json",
        snapshots["currency_selt_securities_sample.json"],
    )
    _write_json(
        FIXTURE_DIR / "moex_currency_boards_sample.json",
        snapshots["currency_selt_boards.json"],
    )
    if "currency_selt_candles_sample.json" in snapshots:
        _write_json(
            FIXTURE_DIR / "moex_currency_candles_sample.json",
            snapshots["currency_selt_candles_sample.json"],
        )

    print(f"Saved MOEX ISS snapshots to {SNAPSHOT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
