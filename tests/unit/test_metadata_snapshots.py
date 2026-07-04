from __future__ import annotations

from datetime import datetime

from moex_iss_adapter.metadata import normalize_futures_metadata
from moex_iss_adapter.storage import list_metadata_snapshots, save_normalized_futures_metadata


def _save_snapshot(response: dict, tmp_path, snapshot_ts: datetime, market: str = "forts") -> None:
    frame = normalize_futures_metadata(
        response,
        snapshot_ts=snapshot_ts,
        engine="futures",
        market=market,
    )
    save_normalized_futures_metadata(
        frame=frame,
        data_root=tmp_path,
        engine="futures",
        market=market,
        snapshot_ts=snapshot_ts,
        overwrite=True,
    )


def test_lists_zero_metadata_snapshots(tmp_path) -> None:
    assert list_metadata_snapshots(data_root=tmp_path) == []


def test_lists_one_futures_metadata_snapshot(futures_securities_response: dict, tmp_path) -> None:
    _save_snapshot(futures_securities_response, tmp_path, datetime(2026, 7, 4, 12, 30, 45))

    snapshots = list_metadata_snapshots(data_root=tmp_path)

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.exchange == "MOEX"
    assert snapshot.engine == "futures"
    assert snapshot.market == "forts"
    assert snapshot.snapshot_ts == "20260704T123045Z"
    assert snapshot.row_count == len(futures_securities_response["securities"]["data"])
    assert snapshot.parquet_path.name == "part-000.parquet"


def test_lists_multiple_metadata_snapshots(futures_securities_response: dict, tmp_path) -> None:
    _save_snapshot(futures_securities_response, tmp_path, datetime(2026, 7, 4, 12, 30, 45))
    _save_snapshot(futures_securities_response, tmp_path, datetime(2026, 7, 4, 12, 31, 45))

    snapshots = list_metadata_snapshots(data_root=tmp_path, include_row_count=False)

    assert [snapshot.snapshot_ts for snapshot in snapshots] == [
        "20260704T123045Z",
        "20260704T123145Z",
    ]
    assert all(snapshot.row_count is None for snapshot in snapshots)


def test_filters_metadata_snapshots_by_engine_and_market(
    futures_securities_response: dict,
    tmp_path,
) -> None:
    _save_snapshot(futures_securities_response, tmp_path, datetime(2026, 7, 4, 12, 30, 45))
    _save_snapshot(
        futures_securities_response,
        tmp_path,
        datetime(2026, 7, 4, 12, 31, 45),
        market="other",
    )

    snapshots = list_metadata_snapshots(data_root=tmp_path, engine="futures", market="forts")

    assert len(snapshots) == 1
    assert snapshots[0].market == "forts"


def test_ignores_unrelated_metadata_files(futures_securities_response: dict, tmp_path) -> None:
    _save_snapshot(futures_securities_response, tmp_path, datetime(2026, 7, 4, 12, 30, 45))
    unrelated = tmp_path / "normalized" / "metadata" / "random" / "part-000.parquet"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text("not parquet", encoding="utf-8")

    snapshots = list_metadata_snapshots(data_root=tmp_path)

    assert len(snapshots) == 1
    assert snapshots[0].snapshot_ts == "20260704T123045Z"
