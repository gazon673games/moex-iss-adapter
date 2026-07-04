"""Support functions for refreshing checked-in MOEX ISS snapshots."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from moex_iss_adapter.constants import (
    DEFAULT_BASE_URL,
    DEFAULT_CURRENCY_ENGINE,
    DEFAULT_CURRENCY_MARKET,
    DEFAULT_FUTURES_ENGINE,
    DEFAULT_FUTURES_MARKET,
    DEFAULT_TIMEFRAME,
)
from moex_iss_adapter.currency import parse_currency_securities
from moex_iss_adapter.endpoints import (
    build_boards_path,
    build_candles_request,
    build_engines_path,
    build_market_securities_path,
    build_markets_path,
    build_securities_columns_path,
)
from moex_iss_adapter.futures import parse_futures_securities
from moex_iss_adapter.metadata import current_snapshot_ts, normalize_futures_metadata
from moex_iss_adapter.storage import save_normalized_futures_metadata, save_raw_futures_metadata
from snapshot.outputs import write_outputs
from snapshot.sampling import (
    choose_currency_candidate,
    choose_futures_candidate,
    sample_currency_securities,
    sample_futures_securities,
)


def fetch_json(client: httpx.Client, path: str, params: dict[str, Any] | None = None) -> Any:
    response = client.get(path, params=params)
    response.raise_for_status()
    return response.json()


def build_snapshot_requests() -> dict[str, tuple[str, dict[str, Any] | None]]:
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
    return {
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


def add_futures_snapshots(
    *,
    client: httpx.Client,
    snapshots: dict[str, Any],
    snapshot_dir: Path,
    root: Path,
) -> None:
    futures_securities = fetch_json(
        client,
        build_market_securities_path(DEFAULT_FUTURES_ENGINE, DEFAULT_FUTURES_MARKET),
    )
    metadata_snapshot_ts = current_snapshot_ts()
    normalized_metadata = normalize_futures_metadata(
        futures_securities,
        snapshot_ts=metadata_snapshot_ts,
    )
    futures_candidates = parse_futures_securities(futures_securities)
    selected_futures, selection_note = choose_futures_candidate(futures_candidates)
    snapshots["futures_forts_securities_sample.json"] = sample_futures_securities(
        futures_securities
    )

    raw_metadata_path = save_raw_futures_metadata(
        response=futures_securities,
        data_root=snapshot_dir,
        engine=DEFAULT_FUTURES_ENGINE,
        market=DEFAULT_FUTURES_MARKET,
        snapshot_ts=metadata_snapshot_ts,
        overwrite=True,
    )
    normalized_metadata_path = save_normalized_futures_metadata(
        frame=normalized_metadata,
        data_root=snapshot_dir,
        engine=DEFAULT_FUTURES_ENGINE,
        market=DEFAULT_FUTURES_MARKET,
        snapshot_ts=metadata_snapshot_ts,
        overwrite=True,
    )
    metadata: dict[str, Any] = {
        "selection_note": selection_note,
        "metadata_snapshot_ts": metadata_snapshot_ts.isoformat(),
        "raw_metadata_path": str(raw_metadata_path.relative_to(root)),
        "normalized_metadata_path": str(normalized_metadata_path.relative_to(root)),
        "selected_security": selected_futures.model_dump() if selected_futures else None,
    }
    if selected_futures is not None:
        from_date = "2023-01-10" if selected_futures.secid == "CNYRUBF" else "2026-07-01"
        till_date = "2023-01-20" if selected_futures.secid == "CNYRUBF" else "2026-07-03"
        path, params = build_candles_request(
            engine=DEFAULT_FUTURES_ENGINE,
            market=DEFAULT_FUTURES_MARKET,
            board=None,
            security=selected_futures.secid,
            from_date=from_date,
            till_date=till_date,
            timeframe=DEFAULT_TIMEFRAME,
            start=0,
        )
        snapshots["futures_forts_candles_sample.json"] = fetch_json(client, path, params)
        metadata["candles"] = {"from": from_date, "till": till_date, "path": path, "params": params}
    snapshots["futures_snapshot_metadata.json"] = metadata


def add_currency_snapshots(client: httpx.Client, snapshots: dict[str, Any]) -> None:
    currency_securities = fetch_json(
        client,
        build_market_securities_path(DEFAULT_CURRENCY_ENGINE, DEFAULT_CURRENCY_MARKET),
    )
    currency_candidates = parse_currency_securities(currency_securities)
    selected_currency, selection_note = choose_currency_candidate(currency_candidates)
    snapshots["currency_selt_securities_sample.json"] = sample_currency_securities(
        currency_securities
    )

    metadata: dict[str, Any] = {
        "selection_note": selection_note,
        "selected_security": selected_currency.model_dump() if selected_currency else None,
    }
    if selected_currency is not None:
        path, params = build_candles_request(
            engine=DEFAULT_CURRENCY_ENGINE,
            market=DEFAULT_CURRENCY_MARKET,
            board=None,
            security=selected_currency.secid,
            from_date="2023-01-10",
            till_date="2023-01-20",
            timeframe=DEFAULT_TIMEFRAME,
            start=0,
        )
        snapshots["currency_selt_candles_sample.json"] = fetch_json(client, path, params)
        metadata["candles"] = {
            "from": "2023-01-10",
            "till": "2023-01-20",
            "path": path,
            "params": params,
        }
    snapshots["currency_snapshot_metadata.json"] = metadata


def refresh_snapshots(*, root: Path) -> None:
    snapshot_dir = root / "docs" / "moex_iss" / "snapshots"
    fixture_dir = root / "tests" / "fixtures"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    fixture_dir.mkdir(parents=True, exist_ok=True)

    with httpx.Client(base_url=DEFAULT_BASE_URL, timeout=20.0, follow_redirects=True) as client:
        snapshots = {
            filename: fetch_json(client, path, params)
            for filename, (path, params) in build_snapshot_requests().items()
        }
        add_futures_snapshots(
            client=client, snapshots=snapshots, snapshot_dir=snapshot_dir, root=root
        )
        add_currency_snapshots(client, snapshots)

    write_outputs(snapshot_dir=snapshot_dir, fixture_dir=fixture_dir, snapshots=snapshots)
