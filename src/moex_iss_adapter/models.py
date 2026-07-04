"""Pydantic models used by the MOEX ISS adapter."""

from __future__ import annotations

from datetime import date, datetime
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


class FuturesChainContract(AdapterBaseModel):
    """Concrete futures contract selected from normalized metadata."""

    secid: str
    board: str
    shortname: str | None = None
    secname: str | None = None
    assetcode: str | None = None
    last_trade_date: date | None = None
    expiration_date: date | None = None


class FuturesBulkSkip(AdapterBaseModel):
    """One futures contract or candidate skipped during bulk preparation."""

    secid: str | None = None
    board: str | None = None
    reason: str


class FuturesChainSelection(AdapterBaseModel):
    """Metadata filtering result for a futures chain preparation run."""

    contracts_found: int
    contracts: list[FuturesChainContract] = Field(default_factory=list)
    skipped: list[FuturesBulkSkip] = Field(default_factory=list)


class FuturesBulkResult(AdapterBaseModel):
    """End-to-end result for futures bulk candle preparation."""

    metadata_snapshot: MetadataSnapshotResult
    contracts_found: int
    selected_contracts: list[FuturesChainContract] = Field(default_factory=list)
    download_results: list[DownloadResult] = Field(default_factory=list)
    skipped_contracts: list[FuturesBulkSkip] = Field(default_factory=list)

    @property
    def metadata_snapshot_ts(self) -> datetime:
        return self.metadata_snapshot.snapshot_ts

    @property
    def contracts_selected(self) -> int:
        return len(self.selected_contracts)

    @property
    def contracts_downloaded(self) -> int:
        return len(self.download_results)

    @property
    def contracts_skipped(self) -> int:
        return len(self.skipped_contracts)

    @property
    def rows_total(self) -> int:
        return sum(result.row_count for result in self.download_results)

    @property
    def normalized_paths(self) -> list[Path]:
        return [
            result.normalized_path
            for result in self.download_results
            if result.normalized_path is not None
        ]
