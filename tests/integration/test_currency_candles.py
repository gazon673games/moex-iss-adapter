from __future__ import annotations

import polars as pl
import pytest

from moex_iss_adapter.currency import is_cny_or_usd_related_currency
from moex_iss_adapter.downloader import download_currency_candles, fetch_currency_securities
from moex_iss_adapter.exceptions import MoexHttpError, MoexIssAdapterError
from moex_iss_adapter.models import MoexIssConfig


@pytest.mark.integration
def test_discover_and_download_currency_candles(tmp_path) -> None:
    config = MoexIssConfig(timeout_seconds=10.0, max_retries=1, max_pages=10)
    try:
        securities = fetch_currency_securities(config=config)
    except MoexHttpError as exc:
        pytest.skip(f"MOEX ISS is not reachable from this environment: {exc}")

    candidates = [security for security in securities if is_cny_or_usd_related_currency(security)]
    if not candidates:
        pytest.skip("No CNY/USD-related currency instrument is currently available from MOEX ISS")

    preferred = next(
        (security for security in candidates if security.secid == "CNY000000TOD"), None
    )
    candidate = preferred or candidates[0]

    try:
        result = download_currency_candles(
            symbol=candidate.secid,
            timeframe="1d",
            from_date="2023-01-10",
            till_date="2023-01-20",
            save_raw=True,
            save_normalized=True,
            data_root=tmp_path,
            overwrite=True,
            config=config,
        )
    except MoexIssAdapterError as exc:
        pytest.skip(f"Could not download currency candles for {candidate.secid}: {exc}")

    if result.row_count == 0:
        pytest.skip(f"MOEX ISS returned no currency candle rows for {candidate.secid}")

    assert result.engine == "currency"
    assert result.market == "selt"
    assert result.board
    assert result.quality_report.passed
    assert result.raw_path is not None and result.raw_path.exists()
    assert result.normalized_path is not None and result.normalized_path.exists()
    assert pl.read_parquet(result.normalized_path).height == result.row_count
