from __future__ import annotations

from datetime import datetime

import polars as pl
import pytest

from moex_iss_adapter.constants import FUTURES_METADATA_COLUMNS
from moex_iss_adapter.exceptions import MoexResponseFormatError
from moex_iss_adapter.metadata import (
    load_futures_metadata_snapshot,
    normalize_futures_metadata,
    search_futures_metadata,
)
from moex_iss_adapter.quality import validate_futures_metadata
from moex_iss_adapter.storage import (
    build_normalized_futures_metadata_path,
    build_raw_futures_metadata_path,
    save_normalized_futures_metadata,
    save_raw_futures_metadata,
)

SNAPSHOT_TS = datetime(2026, 7, 4, 12, 30, 45)


def test_normalizes_futures_metadata_schema(futures_securities_response: dict) -> None:
    frame = normalize_futures_metadata(futures_securities_response, snapshot_ts=SNAPSHOT_TS)

    assert frame.columns == list(FUTURES_METADATA_COLUMNS)
    assert frame.height == len(futures_securities_response["securities"]["data"])
    assert set(frame["source"].to_list()) == {"moex"}
    assert set(frame["exchange"].to_list()) == {"MOEX"}
    assert set(frame["engine"].to_list()) == {"futures"}
    assert set(frame["market"].to_list()) == {"forts"}
    assert "CNYRUBF" in set(frame["secid"].to_list())
    assert frame.schema["snapshot_ts"] == pl.Datetime
    assert frame["raw_metadata"].str.contains('"secid"', literal=True).all()


def test_normalizes_missing_optional_futures_metadata_fields() -> None:
    response = {
        "securities": {
            "columns": ["SECID", "BOARDID"],
            "data": [["TEST1", "RFUD"]],
        }
    }

    frame = normalize_futures_metadata(response, snapshot_ts=SNAPSHOT_TS)
    row = frame.row(0, named=True)

    assert row["secid"] == "TEST1"
    assert row["board"] == "RFUD"
    assert row["shortname"] is None
    assert row["assetcode"] is None
    assert row["lot_size"] is None


def test_empty_metadata_response_returns_empty_schema(
    futures_securities_empty_response: dict,
) -> None:
    frame = normalize_futures_metadata(futures_securities_empty_response, snapshot_ts=SNAPSHOT_TS)

    assert frame.columns == list(FUTURES_METADATA_COLUMNS)
    assert frame.height == 0


def test_malformed_metadata_response_raises(
    futures_securities_malformed_response: dict,
) -> None:
    with pytest.raises(MoexResponseFormatError, match="missing SECID"):
        normalize_futures_metadata(futures_securities_malformed_response, snapshot_ts=SNAPSHOT_TS)


def test_metadata_quality_detects_duplicates(futures_securities_response: dict) -> None:
    frame = normalize_futures_metadata(futures_securities_response, snapshot_ts=SNAPSHOT_TS)
    duplicate = pl.concat([frame, frame.head(1)])

    report = validate_futures_metadata(duplicate)

    assert not report.passed
    assert report.duplicate_count == 1
    assert any("Duplicate futures metadata rows" in issue for issue in report.issues)


def test_metadata_quality_checks_required_values(futures_securities_response: dict) -> None:
    frame = normalize_futures_metadata(futures_securities_response, snapshot_ts=SNAPSHOT_TS)

    report = validate_futures_metadata(frame.with_columns(pl.lit("other").alias("source")))

    assert not report.passed
    assert any("Column source must equal" in issue for issue in report.issues)


def test_metadata_storage_paths(tmp_path) -> None:
    raw_path = build_raw_futures_metadata_path(
        data_root=tmp_path,
        engine="futures",
        market="forts",
        snapshot_ts=SNAPSHOT_TS,
    )
    normalized_path = build_normalized_futures_metadata_path(
        data_root=tmp_path,
        engine="futures",
        market="forts",
        snapshot_ts=SNAPSHOT_TS,
    )

    assert raw_path.as_posix().endswith(
        "raw/moex/metadata/engine=futures/market=forts/securities/snapshot_ts=20260704T123045Z.json"
    )
    assert normalized_path.as_posix().endswith(
        "normalized/metadata/exchange=MOEX/engine=futures/market=forts/securities/"
        "snapshot_ts=20260704T123045Z/part-000.parquet"
    )


def test_saves_and_loads_metadata_parquet(futures_securities_response: dict, tmp_path) -> None:
    frame = normalize_futures_metadata(futures_securities_response, snapshot_ts=SNAPSHOT_TS)
    raw_path = save_raw_futures_metadata(
        response=futures_securities_response,
        data_root=tmp_path,
        engine="futures",
        market="forts",
        snapshot_ts=SNAPSHOT_TS,
    )
    normalized_path = save_normalized_futures_metadata(
        frame=frame,
        data_root=tmp_path,
        engine="futures",
        market="forts",
        snapshot_ts=SNAPSHOT_TS,
    )

    loaded = load_futures_metadata_snapshot(normalized_path)
    assert raw_path.exists()
    assert loaded.columns == frame.columns
    assert loaded.height == frame.height


def test_searches_metadata_by_fields(futures_securities_response: dict) -> None:
    frame = normalize_futures_metadata(futures_securities_response, snapshot_ts=SNAPSHOT_TS)

    assert "CNYRUBF" in set(search_futures_metadata(frame, secid="CNYRUBF")["secid"])
    assert search_futures_metadata(frame, shortname="CNY").height > 0
    assert search_futures_metadata(frame, secname="CNY").height > 0
    assert search_futures_metadata(frame, assetcode="CNY").height > 0
    assert search_futures_metadata(frame, query="CNY").height > 0
