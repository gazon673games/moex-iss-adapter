from __future__ import annotations

from datetime import date
from typing import Any

from moex_iss_adapter.downloads.futures_history import search_historical_futures_contracts
from moex_iss_adapter.futures_history import (
    contract_from_security_details,
    contract_is_expired,
    search_response_futures_secids,
)
from moex_iss_adapter.probes import summarize_endpoint_response


def _global_search_response() -> dict[str, Any]:
    return {
        "securities": {
            "columns": ["secid", "shortname", "group", "type"],
            "data": [
                ["CRH5", "CNY-3.25", "futures_forts", "futures"],
                ["MYH5", "MOEXCNY-3.25", "futures_forts", "futures"],
                ["CRH5CRM5", "CNY spread", "futures_forts", "futures_spread"],
                ["CRM5", "CNY-6.25", "futures_forts", "futures"],
                ["SBER", "SBER", "stock_shares", "common_share"],
            ],
        }
    }


def _details_response(
    *,
    assetcode: str = "CNY",
    expiration_date: str = "2025-03-20",
) -> dict[str, Any]:
    return {
        "description": {
            "columns": ["name", "title", "value", "type"],
            "data": [
                ["SHORTNAME", "Short name", "CNY-3.25", "string"],
                ["SECNAME", "Name", "Futures contract CNY-3.25", "string"],
                ["ASSETCODE", "Asset code", assetcode, "string"],
                ["LSTTRADE", "Last trade date", expiration_date, "date"],
                ["LSTDELDATE", "Last delivery date", expiration_date, "date"],
            ],
        },
        "boards": {
            "columns": [
                "boardid",
                "title",
                "engine",
                "market",
                "is_primary",
                "history_from",
                "history_till",
            ],
            "data": [
                ["RFUD", "FORTS futures", "futures", "forts", 1, "2023-09-08", expiration_date],
                ["RPUA", "Options", "futures", "options", 0, "2023-09-08", expiration_date],
            ],
        },
    }


class FakeHistoryClient:
    def __init__(self) -> None:
        self.starts: list[int] = []

    def search_global_securities(self, query: str, start: int = 0) -> dict[str, Any]:
        assert query == "CNY"
        self.starts.append(start)
        if start > 0:
            return {"securities": {"columns": ["secid"], "data": []}}
        return _global_search_response()

    def get_security_details(self, security: str) -> dict[str, Any]:
        assert security in {"CRH5", "CRM5"}
        return _details_response(
            expiration_date="2025-06-19" if security == "CRM5" else "2025-03-20"
        )


def test_global_search_response_filters_forts_futures_by_prefix() -> None:
    secids = search_response_futures_secids(_global_search_response(), secid_prefix="CR")

    assert secids == ["CRH5", "CRM5"]


def test_contract_from_security_details_extracts_dates_and_board() -> None:
    contract = contract_from_security_details(
        "CRH5",
        _details_response(),
        source_endpoint="/securities/CRH5.json",
    )

    assert contract is not None
    assert contract.secid == "CRH5"
    assert contract.board == "RFUD"
    assert contract.assetcode == "CNY"
    assert contract.expiration_date == date(2025, 3, 20)
    assert contract.last_trade_date == date(2025, 3, 20)
    assert contract.source_endpoint == "/securities/CRH5.json"
    assert contract_is_expired(contract, today=date(2026, 7, 4))


def test_search_historical_futures_contracts_hydrates_filtered_contracts() -> None:
    client = FakeHistoryClient()

    contracts = search_historical_futures_contracts(
        query="CNY",
        secid_prefix="CR",
        asset_code="CNY",
        exclude_secids=["CRM5"],
        client=client,  # type: ignore[arg-type]
    )

    assert [contract.secid for contract in contracts] == ["CRH5"]
    assert contracts[0].metadata_found
    assert client.starts == [0, 5]


def test_endpoint_probe_parser_summarizes_fixture_response() -> None:
    summary = summarize_endpoint_response(
        endpoint="global_search_cny",
        status="200",
        response=_global_search_response(),
        notes="bounded fixture",
    )

    assert summary.endpoint == "global_search_cny"
    assert summary.status == "200"
    assert summary.rows == 5
    assert summary.sample_secids[:3] == ["CRH5", "MYH5", "CRH5CRM5"]
    assert "first_table=securities" in summary.notes
