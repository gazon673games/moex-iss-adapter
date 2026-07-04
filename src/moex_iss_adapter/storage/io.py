"""Shared low-level storage I/O helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl

from moex_iss_adapter.exceptions import MoexStorageError


def ensure_writable(path: Path, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        msg = f"Refusing to overwrite existing file without overwrite=True: {path}"
        raise MoexStorageError(msg)
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json_payload(path: Path, payload: Any, *, error_message: str) -> None:
    try:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise MoexStorageError(error_message) from exc


def write_parquet_frame(path: Path, frame: pl.DataFrame, *, error_message: str) -> None:
    try:
        frame.write_parquet(path)
    except Exception as exc:  # pragma: no cover - backend exception types vary by version.
        raise MoexStorageError(error_message) from exc
