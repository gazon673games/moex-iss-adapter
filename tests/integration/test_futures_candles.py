from __future__ import annotations

import pytest

from moex_iss_adapter.downloader import download_futures_candles, fetch_futures_securities
from moex_iss_adapter.exceptions import MoexHttpError, MoexIssAdapterError
from moex_iss_adapter.futures import is_cny_related_futures
from moex_iss_adapter.models import MoexIssConfig


@pytest.mark.integration
def test_discover_and_download_cny_related_futures_candles(tmp_path) -> None:
    config = MoexIssConfig(timeout_seconds=10.0, max_retries=1, max_pages=10)
    try:
        securities = fetch_futures_securities(config=config)
    except MoexHttpError as exc:
        pytest.skip(f"MOEX ISS is not reachable from this environment: {exc}")

    candidates = [security for security in securities if is_cny_related_futures(security)]
    if not candidates:
        pytest.skip("No CNY/RUB-related futures contract is currently available from MOEX ISS")

    preferred = next((security for security in candidates if security.secid == "CNYRUBF"), None)
    candidate = preferred or max(candidates, key=lambda security: security.prevopenposition or 0)
    from_date = "2023-01-10" if candidate.secid == "CNYRUBF" else "2026-07-01"
    till_date = "2023-01-20" if candidate.secid == "CNYRUBF" else "2026-07-03"

    try:
        result = download_futures_candles(
            symbol=candidate.secid,
            timeframe="1d",
            from_date=from_date,
            till_date=till_date,
            save_raw=True,
            save_normalized=True,
            data_root=tmp_path,
            overwrite=True,
            config=config,
        )
    except MoexIssAdapterError as exc:
        pytest.skip(f"Could not download futures candles for {candidate.secid}: {exc}")

    if result.row_count == 0:
        pytest.skip(f"MOEX ISS returned no futures candle rows for {candidate.secid}")

    assert result.engine == "futures"
    assert result.market == "forts"
    assert result.board
    assert result.quality_report.passed
    assert result.raw_path is not None and result.raw_path.exists()
    assert result.normalized_path is not None and result.normalized_path.exists()
