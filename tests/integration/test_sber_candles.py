from __future__ import annotations

import pytest

from moex_iss_adapter.downloader import download_candles
from moex_iss_adapter.exceptions import MoexHttpError
from moex_iss_adapter.models import MoexIssConfig


@pytest.mark.integration
def test_download_sber_tqbr_daily_candles_from_live_moex(tmp_path) -> None:
    try:
        result = download_candles(
            symbol="SBER",
            engine="stock",
            market="shares",
            board="TQBR",
            timeframe="1d",
            from_date="2023-01-10",
            till_date="2023-01-20",
            save_raw=True,
            save_normalized=True,
            data_root=tmp_path,
            overwrite=True,
            config=MoexIssConfig(timeout_seconds=10.0, max_retries=1, max_pages=10),
        )
    except MoexHttpError as exc:
        pytest.skip(f"MOEX ISS is not reachable from this environment: {exc}")

    assert result.row_count > 0
    assert result.quality_report.passed
    assert result.raw_path is not None and result.raw_path.exists()
    assert result.normalized_path is not None and result.normalized_path.exists()
