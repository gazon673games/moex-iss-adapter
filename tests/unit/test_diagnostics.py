from __future__ import annotations

from datetime import datetime

import polars as pl

from moex_iss_adapter.diagnostics import (
    find_normalized_candle_paths,
    intraday_coverage_record,
    write_intraday_coverage_report,
)


def test_intraday_coverage_record_computes_core_fields() -> None:
    frame = _fixture_5m_frame()

    record = intraday_coverage_record(frame)

    assert record["symbol"] == "CRU6"
    assert record["row_count"] == 4
    assert record["min_ts"] == datetime(2026, 7, 1, 10, 0)
    assert record["max_ts"] == datetime(2026, 7, 2, 10, 5)
    assert record["trading_day_count"] == 2
    assert record["duplicate_ts_count"] == 0
    assert record["null_ohlc_count"] == 0
    assert record["max_intraday_gap_minutes"] == 40.0
    assert record["large_gap_count"] == 1


def test_write_intraday_coverage_report_writes_json_and_csv(tmp_path) -> None:
    parquet_path = tmp_path / "CRU6.parquet"
    json_path = tmp_path / "coverage.json"
    csv_path = tmp_path / "coverage.csv"
    _fixture_5m_frame().write_parquet(parquet_path)

    report = write_intraday_coverage_report([parquet_path], json_path=json_path, csv_path=csv_path)

    assert report["summary"]["contracts_reported"] == 1
    assert report["summary"]["total_rows"] == 4
    assert json_path.exists()
    assert csv_path.exists()
    assert "CRU6" in json_path.read_text(encoding="utf-8")


def test_find_normalized_candle_paths_filters_by_timeframe_and_prefix(tmp_path) -> None:
    wanted = (
        tmp_path
        / "normalized"
        / "candles"
        / "exchange=MOEX"
        / "engine=futures"
        / "market=forts"
        / "board=RFUD"
        / "symbol=CRU6"
        / "timeframe=5m"
        / "part-000.parquet"
    )
    ignored = wanted.parents[1] / "timeframe=1d" / "part-000.parquet"
    wanted.parent.mkdir(parents=True)
    ignored.parent.mkdir(parents=True)
    _fixture_5m_frame().write_parquet(wanted)
    _fixture_5m_frame().write_parquet(ignored)

    paths = find_normalized_candle_paths(
        data_root=tmp_path,
        timeframe="5m",
        symbol_prefix="CR",
    )

    assert paths == [wanted]


def _fixture_5m_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "source": ["moex"] * 4,
            "exchange": ["MOEX"] * 4,
            "engine": ["futures"] * 4,
            "market": ["forts"] * 4,
            "board": ["RFUD"] * 4,
            "symbol": ["CRU6"] * 4,
            "timeframe": ["5m"] * 4,
            "ts": [
                datetime(2026, 7, 1, 10, 0),
                datetime(2026, 7, 1, 10, 5),
                datetime(2026, 7, 1, 10, 45),
                datetime(2026, 7, 2, 10, 5),
            ],
            "open": [1.0, 1.1, 1.2, 1.3],
            "high": [1.1, 1.2, 1.3, 1.4],
            "low": [0.9, 1.0, 1.1, 1.2],
            "close": [1.05, 1.15, 1.25, 1.35],
            "volume": [10.0, 11.0, 12.0, 13.0],
            "value": [100.0, 110.0, 120.0, 130.0],
            "currency": ["RUB"] * 4,
        }
    )
