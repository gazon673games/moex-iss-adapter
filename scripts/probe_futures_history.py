"""Probe small MOEX ISS endpoint samples relevant to historical FORTS futures."""

from __future__ import annotations

import httpx

from moex_iss_adapter.constants import DEFAULT_BASE_URL
from moex_iss_adapter.probes import EndpointProbeSummary, summarize_endpoint_response

Probe = tuple[str, str, dict[str, object], str]


PROBES: tuple[Probe, ...] = (
    (
        "current_forts_securities",
        "/engines/futures/markets/forts/securities.json",
        {"iss.only": "securities", "q": "CNY", "limit": 10},
        "current market security metadata",
    ),
    (
        "history_market_securities",
        "/history/engines/futures/markets/forts/securities.json",
        {"date": "2025-03-07", "limit": 10},
        "daily historical rows, not full contract metadata",
    ),
    (
        "history_board_securities",
        "/history/engines/futures/markets/forts/boards/RFUD/securities.json",
        {"date": "2025-03-07", "limit": 10},
        "board-specific daily historical rows",
    ),
    (
        "global_search_cny",
        "/securities.json",
        {"iss.only": "securities", "q": "CNY", "start": 0},
        "global search can expose expired futures candidates",
    ),
    (
        "global_detail_crh5",
        "/securities/CRH5.json",
        {},
        "contract details include dates and boards",
    ),
    (
        "expired_board_candles_crh5",
        "/engines/futures/markets/forts/boards/RFUD/securities/CRH5/candles.json",
        {"from": "2025-01-01", "till": "2025-03-31", "interval": 24, "start": 0},
        "bounded candle sample for an expired CR contract",
    ),
)


def _probe_one(client: httpx.Client, probe: Probe) -> EndpointProbeSummary:
    name, path, params, notes = probe
    try:
        response = client.get(path, params=params)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return summarize_endpoint_response(
                endpoint=name,
                status="invalid_json_shape",
                response=None,
                notes=notes,
            )
        return summarize_endpoint_response(
            endpoint=name,
            status=str(response.status_code),
            response=payload,
            notes=notes,
        )
    except (httpx.HTTPError, ValueError) as exc:
        return summarize_endpoint_response(
            endpoint=name,
            status=f"error: {exc}",
            response=None,
            notes=notes,
        )


def _format_summary(summary: EndpointProbeSummary) -> str:
    columns = ",".join(summary.columns)
    sample_secids = ",".join(summary.sample_secids)
    return (
        f"{summary.endpoint} | {summary.status} | {summary.rows} | "
        f"{columns} | {sample_secids} | {summary.notes}"
    )


def main() -> None:
    """Run bounded endpoint probes and print a compact report."""

    print("endpoint | status | rows | columns | sample SECIDs | notes")
    with httpx.Client(base_url=DEFAULT_BASE_URL, timeout=20.0, follow_redirects=True) as client:
        for probe in PROBES:
            print(_format_summary(_probe_one(client, probe)))


if __name__ == "__main__":
    main()
