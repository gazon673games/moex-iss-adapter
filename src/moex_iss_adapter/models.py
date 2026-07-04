"""Pydantic models used by the MOEX ISS adapter."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from moex_iss_adapter.constants import DEFAULT_BASE_URL


class AdapterBaseModel(BaseModel):
    """Common strict model configuration."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)


class MoexIssConfig(AdapterBaseModel):
    """Low-level MOEX ISS client configuration."""

    base_url: str = DEFAULT_BASE_URL
    timeout_seconds: float = Field(default=30.0, gt=0)
    max_retries: int = Field(default=3, ge=0)
    max_pages: int = Field(default=1000, gt=0)
    user_agent: str = "ohlcv-replay/moex_iss_adapter"


class RawMoexCandleRow(AdapterBaseModel):
    """Raw MOEX candle row fields used during parsing."""

    begin: str
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    value: float | None = None
    currency: str | None = None


class CanonicalCandle(AdapterBaseModel):
    """Canonical OHLCV candle shape for one normalized row."""

    source: str
    exchange: str
    engine: str
    market: str
    board: str
    symbol: str
    timeframe: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    value: float | None = None
    currency: str | None = None


class FuturesSecurity(AdapterBaseModel):
    """Selected MOEX futures security metadata used for discovery."""

    secid: str
    boardid: str | None = None
    shortname: str | None = None
    secname: str | None = None
    assetcode: str | None = None
    latname: str | None = None
    lasttradedate: str | None = None
    lastdeldate: str | None = None
    sectype: str | None = None
    lotvolume: float | None = None
    prevopenposition: float | None = None


class CurrencySecurity(AdapterBaseModel):
    """Selected MOEX currency security metadata used for discovery."""

    secid: str
    boardid: str | None = None
    shortname: str | None = None
    secname: str | None = None
    faceunit: str | None = None
    currencyid: str | None = None
    latname: str | None = None
    marketcode: str | None = None
    lotsize: float | None = None
    settledate: str | None = None


class QualityReport(AdapterBaseModel):
    """Structured quality validation result."""

    passed: bool
    row_count: int
    min_ts: datetime | None
    max_ts: datetime | None
    duplicate_count: int
    issues: list[str] = Field(default_factory=list)


class MetadataQualityReport(AdapterBaseModel):
    """Structured futures metadata quality validation result."""

    passed: bool
    row_count: int
    duplicate_count: int
    issues: list[str] = Field(default_factory=list)


class StorageResult(AdapterBaseModel):
    """Paths written by storage operations."""

    raw_path: Path | None = None
    normalized_path: Path | None = None


class DownloadResult(AdapterBaseModel):
    """End-to-end candle download result."""

    symbol: str
    engine: str
    market: str
    board: str
    timeframe: str
    from_date: str
    till_date: str
    row_count: int
    min_ts: datetime | None
    max_ts: datetime | None
    raw_path: Path | None
    normalized_path: Path | None
    quality_report: QualityReport


class MetadataSnapshotResult(AdapterBaseModel):
    """End-to-end futures metadata snapshot result."""

    engine: str
    market: str
    row_count: int
    snapshot_ts: datetime
    raw_path: Path | None
    normalized_path: Path | None
    quality_report: MetadataQualityReport


class MetadataSnapshotInfo(AdapterBaseModel):
    """Saved normalized metadata snapshot descriptor."""

    exchange: str
    engine: str
    market: str
    snapshot_ts: str
    parquet_path: Path
    row_count: int | None = None
