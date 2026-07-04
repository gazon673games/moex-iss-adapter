"""Small helpers for summarizing MOEX ISS endpoint probe responses."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EndpointProbeSummary:
    """Compact endpoint probe result for documentation and scripts."""

    endpoint: str
    status: str
    rows: int
    columns: list[str]
    sample_secids: list[str]
    notes: str


def _first_table(response: Mapping[str, Any]) -> tuple[str | None, Mapping[str, Any] | None]:
    for name, table in response.items():
        if not isinstance(table, Mapping):
            continue
        columns = table.get("columns")
        data = table.get("data")
        if isinstance(columns, list) and isinstance(data, list):
            return str(name), table
    return None, None


def summarize_endpoint_response(
    *,
    endpoint: str,
    status: str,
    response: Mapping[str, Any] | None,
    notes: str = "",
) -> EndpointProbeSummary:
    """Return a compact summary for one MOEX ISS JSON endpoint response."""

    if response is None:
        return EndpointProbeSummary(
            endpoint=endpoint,
            status=status,
            rows=0,
            columns=[],
            sample_secids=[],
            notes=notes,
        )

    table_name, table = _first_table(response)
    if table is None:
        return EndpointProbeSummary(
            endpoint=endpoint,
            status=status,
            rows=0,
            columns=[],
            sample_secids=[],
            notes=notes or "no table-like blocks",
        )

    columns = [str(column) for column in table.get("columns", [])]
    data = table.get("data", [])
    rows = len(data) if isinstance(data, list) else 0
    secid_column = next((column for column in columns if column.lower() == "secid"), None)
    sample_secids: list[str] = []
    if secid_column is not None and isinstance(data, list):
        secid_index = columns.index(secid_column)
        for row in data:
            if not isinstance(row, list) or len(row) <= secid_index:
                continue
            value = row[secid_index]
            if value is None:
                continue
            secid = str(value)
            if secid not in sample_secids:
                sample_secids.append(secid)
            if len(sample_secids) >= 5:
                break

    suffix = f"first_table={table_name}" if table_name else ""
    joined_notes = "; ".join(part for part in (notes, suffix) if part)
    return EndpointProbeSummary(
        endpoint=endpoint,
        status=status,
        rows=rows,
        columns=columns[:12],
        sample_secids=sample_secids,
        notes=joined_notes,
    )
