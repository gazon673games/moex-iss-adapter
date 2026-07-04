"""Standalone MOEX ISS OHLCV adapter."""

from moex_iss_adapter.downloader import (
    download_candles,
    download_futures_candles,
    fetch_futures_securities,
    save_futures_metadata_snapshot,
    search_futures_securities,
    search_saved_futures_metadata,
)
from moex_iss_adapter.models import (
    DownloadResult,
    MetadataSnapshotInfo,
    MetadataSnapshotResult,
    MoexIssConfig,
    QualityReport,
)

__all__ = [
    "DownloadResult",
    "MetadataSnapshotInfo",
    "MetadataSnapshotResult",
    "MoexIssConfig",
    "QualityReport",
    "download_candles",
    "download_futures_candles",
    "fetch_futures_securities",
    "save_futures_metadata_snapshot",
    "search_saved_futures_metadata",
    "search_futures_securities",
]

__version__ = "0.1.0"
