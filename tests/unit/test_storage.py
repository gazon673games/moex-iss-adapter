from __future__ import annotations

import json

import polars as pl
import pytest

from moex_iss_adapter.exceptions import MoexStorageError
from moex_iss_adapter.normalizers import normalize_candles
from moex_iss_adapter.storage import (
    build_normalized_candles_path,
    build_raw_candles_path,
    save_normalized_candles,
    save_raw_candles,
)


def _normalized(response: dict) -> pl.DataFrame:
    return normalize_candles(
        [response],
        engine="stock",
        market="shares",
        board="TQBR",
        symbol="SBER",
        timeframe="1d",
    )


def test_builds_storage_paths(tmp_path) -> None:
    raw_path = build_raw_candles_path(
        data_root=tmp_path,
        engine="stock",
        market="shares",
        board="TQBR",
        symbol="SBER",
        timeframe="1d",
        from_date="2023-01-01",
        till_date="2023-12-31",
    )
    normalized_path = build_normalized_candles_path(
        data_root=tmp_path,
        engine="stock",
        market="shares",
        board="TQBR",
        symbol="SBER",
        timeframe="1d",
    )

    assert raw_path.as_posix().endswith(
        "data/raw/moex/candles/engine=stock/market=shares/board=TQBR/"
        "symbol=SBER/timeframe=1d/from=2023-01-01_till=2023-12-31.json"
    ) or raw_path.as_posix().endswith(
        "raw/moex/candles/engine=stock/market=shares/board=TQBR/"
        "symbol=SBER/timeframe=1d/from=2023-01-01_till=2023-12-31.json"
    )
    assert normalized_path.as_posix().endswith(
        "normalized/candles/exchange=MOEX/engine=stock/market=shares/board=TQBR/"
        "symbol=SBER/timeframe=1d/part-000.parquet"
    )


def test_saves_raw_json(sber_candles_response: dict, tmp_path) -> None:
    path = save_raw_candles(
        responses=[sber_candles_response],
        data_root=tmp_path,
        engine="stock",
        market="shares",
        board="TQBR",
        symbol="SBER",
        timeframe="1d",
        from_date="2023-01-10",
        till_date="2023-01-20",
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["metadata"]["symbol"] == "SBER"
    columns = payload["pages"][0]["candles"]["columns"]
    begin_index = columns.index("begin")
    assert payload["pages"][0]["candles"]["data"][0][begin_index] == "2023-01-10 00:00:00"

    with pytest.raises(MoexStorageError, match="Refusing to overwrite"):
        save_raw_candles(
            responses=[sber_candles_response],
            data_root=tmp_path,
            engine="stock",
            market="shares",
            board="TQBR",
            symbol="SBER",
            timeframe="1d",
            from_date="2023-01-10",
            till_date="2023-01-20",
        )


def test_saves_normalized_parquet(sber_candles_response: dict, tmp_path) -> None:
    frame = _normalized(sber_candles_response)
    path = save_normalized_candles(
        frame=frame,
        data_root=tmp_path,
        engine="stock",
        market="shares",
        board="TQBR",
        symbol="SBER",
        timeframe="1d",
    )

    loaded = pl.read_parquet(path)
    assert loaded.shape == frame.shape
    assert loaded.columns == frame.columns
