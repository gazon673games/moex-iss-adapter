"""Fetch small MOEX ISS snapshots for local documentation and fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from snapshot.support import refresh_snapshots  # noqa: E402


def main() -> int:
    try:
        refresh_snapshots(root=ROOT)
    except httpx.HTTPError as exc:
        print(f"MOEX ISS snapshots were not refreshed: {exc}", file=sys.stderr)
        return 1

    snapshot_dir = ROOT / "docs" / "moex_iss" / "snapshots"
    print(f"Saved MOEX ISS snapshots to {snapshot_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
