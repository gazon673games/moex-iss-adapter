from __future__ import annotations

from datetime import datetime

from moex_iss_adapter.models import (
    QualityReport,
)


def _quality_report() -> QualityReport:
    return QualityReport(
        passed=True,
        row_count=1,
        min_ts=datetime(2023, 1, 10),
        max_ts=datetime(2023, 1, 10),
        duplicate_count=0,
        issues=[],
    )
