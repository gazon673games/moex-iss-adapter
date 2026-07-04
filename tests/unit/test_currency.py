from __future__ import annotations

import pytest

from moex_iss_adapter.currency import (
    find_currency_by_secid,
    is_cny_or_usd_related_currency,
    parse_currency_securities,
    search_currency,
)
from moex_iss_adapter.downloader import download_currency_candles, fetch_currency_securities
from moex_iss_adapter.exceptions import MoexResponseFormatError
from moex_iss_adapter.models import CurrencySecurity, MoexIssConfig
from moex_iss_adapter.normalizers import normalize_candles


class FakeCurrencyClient:
    def __init__(self, securities_response: dict, pages: list[dict] | None = None) -> None:
        self.securities_response = securities_response
        self.pages = pages or []
        self.request_boards: list[str | None] = []

    def get_market_securities(self, engine: str, market: str) -> dict:
        assert engine == "currency"
        assert market == "selt"
        return self.securities_response

    def get_candles_page(self, **kwargs) -> dict:
        self.request_boards.append(kwargs["board"])
        return self.pages.pop(0)


def test_parse_currency_securities_metadata(currency_securities_response: dict) -> None:
    securities = parse_currency_securities(currency_securities_response)

    assert securities[0].secid == "CNY000000TOD"
    assert securities[0].boardid == "CETS"
    assert securities[0].shortname == "CNYRUB_TOD"
    assert securities[0].faceunit == "CNY"
    assert securities[0].currencyid == "RUB"
    assert securities[0].lotsize == 1000.0


def test_search_currency_by_query_and_fields(currency_securities_response: dict) -> None:
    securities = parse_currency_securities(currency_securities_response)

    assert "CNY000000TOD" in {item.secid for item in search_currency(securities, query="CNY")}
    usd_security = next(item for item in securities if "USD" in item.secid)
    assert usd_security in search_currency(securities, secid=usd_security.secid)
    assert [item.secid for item in search_currency(securities, short_name="CNYRUB_TOM")] == [
        "CNYRUB_TOM"
    ]
    assert search_currency(securities, security_name="USD")
    assert all(item.faceunit == "CNY" for item in search_currency(securities, face_unit="CNY"))
    assert search_currency(securities, currency_id="RUB")


def test_empty_currency_search_result(empty_currency_securities_response: dict) -> None:
    securities = parse_currency_securities(empty_currency_securities_response)

    assert securities == []
    assert search_currency(securities, query="CNY") == []


def test_malformed_currency_response_raises(malformed_currency_response: dict) -> None:
    with pytest.raises(MoexResponseFormatError, match="missing SECID"):
        parse_currency_securities(malformed_currency_response)


def test_identifies_cny_or_usd_related_currency(currency_securities_response: dict) -> None:
    securities = parse_currency_securities(currency_securities_response)

    assert is_cny_or_usd_related_currency(find_currency_by_secid(securities, "CNY000000TOD"))
    assert is_cny_or_usd_related_currency(next(item for item in securities if "USD" in item.secid))
    assert not is_cny_or_usd_related_currency(
        CurrencySecurity(secid="EURRUB_TOM", shortname="EURRUB_TOM", faceunit="EUR")
    )


def test_normalizes_currency_candles_with_currency_metadata(
    currency_candles_response: dict,
) -> None:
    frame = normalize_candles(
        [currency_candles_response],
        engine="currency",
        market="selt",
        board="CETS",
        symbol="CNY000000TOD",
        timeframe="1d",
    )

    assert set(frame["engine"].to_list()) == {"currency"}
    assert set(frame["market"].to_list()) == {"selt"}
    assert set(frame["board"].to_list()) == {"CETS"}
    assert set(frame["symbol"].to_list()) == {"CNY000000TOD"}


def test_fetch_currency_securities_uses_market_endpoint(currency_securities_response: dict) -> None:
    client = FakeCurrencyClient(currency_securities_response)

    securities = fetch_currency_securities(client=client)  # type: ignore[arg-type]

    assert securities[0].secid == "CNY000000TOD"
    assert all(security.boardid == "CETS" for security in securities)


def test_download_currency_candles_discovers_board_and_uses_market_endpoint(
    currency_securities_response: dict,
    currency_candles_response: dict,
    empty_candles_response: dict,
    tmp_path,
) -> None:
    client = FakeCurrencyClient(
        currency_securities_response,
        pages=[currency_candles_response, empty_candles_response],
    )
    expected_rows = len(currency_candles_response["candles"]["data"])

    result = download_currency_candles(
        symbol="CNY000000TOD",
        from_date="2023-01-10",
        till_date="2023-01-20",
        save_raw=True,
        save_normalized=True,
        data_root=tmp_path,
        client=client,  # type: ignore[arg-type]
        config=MoexIssConfig(max_pages=10),
    )

    assert client.request_boards == [None, None]
    assert result.engine == "currency"
    assert result.market == "selt"
    assert result.board == "CETS"
    assert result.row_count == expected_rows
    assert result.raw_path is not None and result.raw_path.exists()
    assert result.normalized_path is not None and result.normalized_path.exists()


def test_download_currency_candles_uses_explicit_board(
    currency_securities_response: dict,
    currency_candles_response: dict,
    empty_candles_response: dict,
) -> None:
    client = FakeCurrencyClient(
        currency_securities_response,
        pages=[currency_candles_response, empty_candles_response],
    )

    result = download_currency_candles(
        symbol="CNY000000TOD",
        board="CETS",
        from_date="2023-01-10",
        till_date="2023-01-20",
        client=client,  # type: ignore[arg-type]
        config=MoexIssConfig(max_pages=10),
    )

    assert client.request_boards == ["CETS", "CETS"]
    assert result.board == "CETS"
