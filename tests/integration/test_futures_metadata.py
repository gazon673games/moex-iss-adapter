from __future__ import annotations

import pytest

from moex_iss_adapter.downloader import (
    save_futures_metadata_snapshot,
    search_saved_futures_metadata,
)
from moex_iss_adapter.exceptions import MoexHttpError
from moex_iss_adapter.models import MoexIssConfig


@pytest.mark.integration
def test_save_and_search_live_futures_metadata_snapshot(tmp_path) -> None:
    try:
        result = save_futures_metadata_snapshot(
            save_raw=True,
            save_normalized=True,
            data_root=tmp_path,
            overwrite=True,
            config=MoexIssConfig(timeout_seconds=10.0, max_retries=1),
        )
    except MoexHttpError as exc:
        pytest.skip(f"MOEX ISS is not reachable from this environment: {exc}")

    assert result.row_count > 0
    assert result.quality_report.passed
    assert result.raw_path is not None and result.raw_path.exists()
    assert result.normalized_path is not None and result.normalized_path.exists()

    matches = search_saved_futures_metadata(
        metadata_path=result.normalized_path,
        query="CNY",
    )
    assert isinstance(matches, list)
