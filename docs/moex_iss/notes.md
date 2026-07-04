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
- MOEX currency instruments live under `engine=currency` and `market=selt`.
- Currency SECIDs are not always intuitive, so users should discover/search
  securities first and then download candles for a concrete SECID.
- Currency candles use the same canonical OHLCV schema as shares and futures.
  Currency-specific metadata such as `FACEUNIT`, `CURRENCYID`, `LOTSIZE`, and
  `SETTLEDATE` remains in discovery metadata or raw responses.

## Historical Futures Endpoint Findings

Checked on 2026-07-04 against official MOEX ISS endpoints:

- `/engines/futures/markets/forts/securities.json` returns current and future
  FORTS securities. It is useful for current metadata snapshots, but it is not a
  long expired contract calendar.
- `/history/engines/futures/markets/forts/securities.json` and
  `/history/engines/futures/markets/forts/boards/RFUD/securities.json` return
  historical daily trading rows for a date. They do not provide a compact
  metadata list of expired contracts with full lifecycle fields.
- `/securities.json?q=CNY` returns global security search rows and can expose
  expired FORTS futures candidates when paginated and filtered by
  `group=futures_forts`, `type=futures`, and a family prefix such as `CR`.
- `/securities/<SECID>.json` returns details for current or expired SECIDs when
  MOEX ISS knows the symbol. For `CRH5`, the response included FORTS board
  metadata and lifecycle fields such as first trade, last trade, last delivery,
  and asset code.
- `/engines/futures/markets/forts/boards/RFUD/securities/<SECID>/candles.json`
  can return historical candles for an expired contract such as `CRH5` over a
  bounded date range.

Practical conclusion: the adapter uses global ISS search plus security details
as adapter-level discovery for expired FORTS futures. This is sufficient to
find a longer CR CNY/RUB family when MOEX returns those rows, but it is not
documented here as a guaranteed complete free expired futures calendar. The
CLI also supports explicit `--include-secid` fallback, so known historical
SECIDs can be downloaded even when they are absent from the current metadata
snapshot.

Use `scripts/probe_futures_history.py` for a bounded live probe report. The
script prints endpoint, status, row count, columns, sample SECIDs, and notes
without downloading large datasets.
