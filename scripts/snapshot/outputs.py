"""Write refreshed MOEX ISS snapshots and test fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_outputs(
    *,
    snapshot_dir: Path,
    fixture_dir: Path,
    snapshots: dict[str, Any],
) -> None:
    for filename, payload in snapshots.items():
        write_json(snapshot_dir / filename, payload)

    fixture_names = {
        "moex_candles_sber_tqbr_1d_sample.json": "candles_sber_tqbr_1d_2023-01-10_2023-01-20.json",
        "moex_futures_securities_sample.json": "futures_forts_securities_sample.json",
        "moex_futures_boards_sample.json": "futures_forts_boards.json",
        "moex_futures_candles_sample.json": "futures_forts_candles_sample.json",
        "moex_currency_securities_sample.json": "currency_selt_securities_sample.json",
        "moex_currency_boards_sample.json": "currency_selt_boards.json",
        "moex_currency_candles_sample.json": "currency_selt_candles_sample.json",
    }
    for fixture_name, snapshot_name in fixture_names.items():
        if snapshot_name in snapshots:
            write_json(fixture_dir / fixture_name, snapshots[snapshot_name])
