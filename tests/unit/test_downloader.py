from __future__ import annotations

import polars as pl
import pytest

from moex_iss_adapter.downloader import (
    download_candles,
    save_futures_metadata_snapshot,
    search_saved_futures_metadata,
)
from moex_iss_adapter.exceptions import MoexPaginationError
from moex_iss_adapter.models import MoexIssConfig


class FakeClient:
    def __init__(self, pages: list[dict]) -> None:
        self.pages = pages
        self.starts: list[int] = []

    def get_candles_page(self, **kwargs) -> dict:
        self.starts.append(kwargs["start"])
        if len(self.pages) == 1:
            return self.pages[0]
        return self.pages.pop(0)


class FakeMetadataClient:
    def __init__(self, response: dict) -> None:
        self.response = response

    def get_market_securities(self, engine: str, market: str) -> dict:
        assert engine == "futures"
        assert market == "forts"
        return self.response


def test_download_candles_paginates_normalizes_and_saves(
    sber_candles_response: dict,
    empty_candles_response: dict,
    tmp_path,
) -> None:
    client = FakeClient([sber_candles_response, empty_candles_response])
    expected_rows = len(sber_candles_response["candles"]["data"])

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
        client=client,  # type: ignore[arg-type]
        config=MoexIssConfig(max_pages=10),
    )

    assert client.starts == [0, expected_rows]
    assert result.row_count == expected_rows
    assert result.quality_report.passed
    assert result.raw_path is not None and result.raw_path.exists()
    assert result.normalized_path is not None and result.normalized_path.exists()
    assert pl.read_parquet(result.normalized_path).height == expected_rows


def test_download_candles_raises_when_max_pages_reached(sber_candles_response: dict) -> None:
    client = FakeClient([sber_candles_response])

    with pytest.raises(MoexPaginationError, match="max_pages=1"):
        download_candles(
            symbol="SBER",
            from_date="2023-01-10",
            till_date="2023-01-20",
            client=client,  # type: ignore[arg-type]
            config=MoexIssConfig(max_pages=1),
        )


def test_save_futures_metadata_snapshot_and_search_saved(
    futures_securities_response: dict,
    tmp_path,
) -> None:
    result = save_futures_metadata_snapshot(
        save_raw=True,
        save_normalized=True,
        data_root=tmp_path,
        overwrite=True,
        client=FakeMetadataClient(futures_securities_response),  # type: ignore[arg-type]
    )

    assert result.engine == "futures"
    assert result.market == "forts"
    assert result.quality_report.passed
    assert result.raw_path is not None and result.raw_path.exists()
    assert result.normalized_path is not None and result.normalized_path.exists()

    matches = search_saved_futures_metadata(
        metadata_path=result.normalized_path,
        secid="CNYRUBF",
    )
    assert matches
    assert matches[0].secid == "CNYRUBF"
