# MOEX ISS Implementation Notes

- MOEX ISS often returns table-like JSON objects with `columns` and `data`.
- Normalization parses by column name, not only by fixed column position.
- Candle timestamps from MOEX may appear as `begin`; normalized data must use
  `ts`.
- Pagination is handled through `start`.
- The adapter preserves raw responses separately from normalized data.
- Checked-in test fixtures are small synthetic MOEX-shaped examples. Run
  `scripts/snapshot_moex_iss.py` to refresh live snapshots when MOEX ISS is
  reachable.
- MOEX futures live under `engine=futures` and `market=forts`.
- Futures contracts are expiring instruments. The adapter downloads candles for
  concrete futures SECIDs and does not create synthetic continuous futures.
- Futures metadata such as `ASSETCODE`, `SHORTNAME`, `SECNAME`, `BOARDID`,
  `LASTTRADEDATE`, and `LASTDELDATE` stays in futures discovery metadata. It is
  not added to the canonical OHLCV schema.
- The futures candle endpoint is available in both market-level form and
  board-specific form. The adapter discovers the board from the futures
  securities metadata when the CLI caller omits `--board`.
- Futures securities metadata snapshots are stored separately from candles.
  Raw metadata responses live under `raw/moex/metadata`, while normalized
  metadata Parquet lives under `normalized/metadata`.
- Normalized futures metadata snapshots include a `snapshot_ts` column and a
  `raw_metadata` JSON string so searches can be reproduced against the exact
  discovered security set.
