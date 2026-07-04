from __future__ import annotations

from moex_iss_adapter.downloader import download_futures_candles, fetch_futures_securities
from moex_iss_adapter.futures import (
    find_futures_by_secid,
    is_cny_related_futures,
    parse_futures_securities,
    search_futures,
)
from moex_iss_adapter.models import FuturesSecurity, MoexIssConfig
from moex_iss_adapter.normalizers import normalize_candles


class FakeFuturesClient:
    def __init__(self, securities_response: dict, pages: list[dict] | None = None) -> None:
        self.securities_response = securities_response
        self.pages = pages or []
        self.request_boards: list[str | None] = []

    def get_market_securities(self, engine: str, market: str) -> dict:
        assert engine == "futures"
        assert market == "forts"
        return self.securities_response

    def get_candles_page(self, **kwargs) -> dict:
        self.request_boards.append(kwargs["board"])
        return self.pages.pop(0)


def test_parse_futures_securities_metadata(futures_securities_response: dict) -> None:
    securities = parse_futures_securities(futures_securities_response)

    assert securities[0].secid == "CNYRUBF"
    assert securities[0].boardid == "RFUD"
    assert securities[0].assetcode == "CNYRUBTOM"
    assert securities[0].lasttradedate
    assert securities[0].lotvolume == 1000.0


def test_filter_futures_by_query_asset_short_and_security_name(
    futures_securities_response: dict,
) -> None:
    securities = parse_futures_securities(futures_securities_response)

    query_results = search_futures(securities, query="cny")
    assert "CNYRUBF" in {item.secid for item in query_results}
    assert all(
        "CNY" in (item.shortname or item.secid) or "CNY" in (item.assetcode or "")
        for item in query_results
    )

    asset_results = search_futures(securities, asset_code="UCNY")
    assert asset_results
    assert all("UCNY" in (item.assetcode or "") for item in asset_results)

    short_results = search_futures(securities, short_name="CNY")
    assert short_results
    assert all("CNY" in (item.shortname or "") for item in short_results)

    name_results = search_futures(securities, security_name="CNY")
    assert name_results
    assert all("CNY" in (item.secname or "") for item in name_results)


def test_handles_empty_futures_search_result(empty_futures_securities_response: dict) -> None:
    securities = parse_futures_securities(empty_futures_securities_response)

    assert securities == []
    assert search_futures(securities, query="CNY") == []


def test_identifies_cny_related_futures(futures_securities_response: dict) -> None:
    securities = parse_futures_securities(futures_securities_response)

    assert is_cny_related_futures(find_futures_by_secid(securities, "CNYRUBF"))
    assert not is_cny_related_futures(
        FuturesSecurity(secid="SRU6", shortname="SBER-9.26", assetcode="SBER")
    )


def test_normalizes_futures_candles_with_futures_metadata(futures_candles_response: dict) -> None:
    frame = normalize_candles(
        [futures_candles_response],
        engine="futures",
        market="forts",
        board="RFUD",
        symbol="CNYRUBF",
        timeframe="1d",
    )

    assert set(frame["engine"].to_list()) == {"futures"}
    assert set(frame["market"].to_list()) == {"forts"}
    assert set(frame["board"].to_list()) == {"RFUD"}
    assert set(frame["symbol"].to_list()) == {"CNYRUBF"}


def test_fetch_futures_securities_uses_market_endpoint(futures_securities_response: dict) -> None:
    client = FakeFuturesClient(futures_securities_response)

    securities = fetch_futures_securities(client=client)  # type: ignore[arg-type]

    assert securities[0].secid == "CNYRUBF"
    assert all(security.boardid == "RFUD" for security in securities)


def test_download_futures_candles_discovers_board_and_uses_market_endpoint(
    futures_securities_response: dict,
    futures_candles_response: dict,
    empty_candles_response: dict,
    tmp_path,
) -> None:
    client = FakeFuturesClient(
        futures_securities_response,
        pages=[futures_candles_response, empty_candles_response],
    )
    expected_rows = len(futures_candles_response["candles"]["data"])

    result = download_futures_candles(
        symbol="CNYRUBF",
        from_date="2023-01-10",
        till_date="2023-01-20",
        save_raw=True,
        save_normalized=True,
        data_root=tmp_path,
        client=client,  # type: ignore[arg-type]
        config=MoexIssConfig(max_pages=10),
    )

    assert client.request_boards == [None, None]
    assert result.engine == "futures"
    assert result.market == "forts"
    assert result.board == "RFUD"
    assert result.row_count == expected_rows
    assert result.raw_path is not None and result.raw_path.exists()
    assert result.normalized_path is not None and result.normalized_path.exists()


def test_download_futures_candles_uses_explicit_board(
    futures_securities_response: dict,
    futures_candles_response: dict,
    empty_candles_response: dict,
) -> None:
    client = FakeFuturesClient(
        futures_securities_response,
        pages=[futures_candles_response, empty_candles_response],
    )

    result = download_futures_candles(
        symbol="CNYRUBF",
        board="RFUD",
        from_date="2023-01-10",
        till_date="2023-01-20",
        client=client,  # type: ignore[arg-type]
        config=MoexIssConfig(max_pages=10),
    )

    assert client.request_boards == ["RFUD", "RFUD"]
    assert result.board == "RFUD"
