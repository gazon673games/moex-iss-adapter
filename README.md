# moex_iss_adapter

Standalone adapter for MOEX ISS market data inside `ohlcv-replay`.

The adapter fetches MOEX ISS responses, preserves raw JSON, normalizes candles
to one canonical OHLCV schema, writes Parquet, and runs adapter-level quality
checks. It is not a backtest engine.

## Supported Scope

- Source: MOEX ISS.
- Data type: candles.
- Primary stock scenario: `stock` / `shares` / `TQBR` / `SBER` / `1d`.
- Futures: discovery and candles for concrete `futures` / `forts` SECIDs.
- Currency: discovery and candles for concrete `currency` / `selt` SECIDs.
- Storage: local files under `data/raw` and `data/normalized`.

Unsupported: strategies, signals, order simulation, portfolio accounting,
visualization, web APIs, and server/database orchestration.

Architecture notes:

- `docs/architecture/adapter_scope.md`
- `docs/architecture/adapter_v0_1_audit.md`

## Setup

```bash
uv sync --extra dev
```

```bash
python -m pip install -e ".[dev]"
```

## MOEX ISS Sources

- Official ISS reference: https://iss.moex.com/iss/reference/
- MOEX ISS developer manual: https://www.moex.com/en/documents/8888
- ISS service description: https://www.moex.com/a2920
- Local notes: `docs/moex_iss/sources.md`
- Endpoint registry: `docs/moex_iss/endpoint_registry.yaml`

Refresh checked-in samples:

```bash
uv run python scripts/snapshot_moex_iss.py
```

The snapshot script fetches small deterministic samples for engines, markets,
boards, SBER candles, futures metadata/candles, and currency metadata/candles.
Default tests use fixtures and do not require network access.

## CLI

Stock/share candles:

```bash
uv run moex-iss candles \
  --symbol SBER \
  --engine stock \
  --market shares \
  --board TQBR \
  --timeframe 1d \
  --from-date 2020-01-01 \
  --till-date 2024-12-31 \
  --save-raw \
  --save-normalized
```

Futures discovery and candles:

```bash
uv run moex-iss futures search --query CNY
uv run moex-iss futures candles \
  --symbol CNYRUBF \
  --timeframe 1d \
  --from-date 2023-01-10 \
  --till-date 2023-01-20 \
  --save-raw \
  --save-normalized
```

Currency discovery and candles:

```bash
uv run moex-iss currency search --query CNY
uv run moex-iss currency search --query USD
uv run moex-iss currency candles \
  --symbol <DISCOVERED_CURRENCY_SECID> \
  --timeframe 1d \
  --from-date 2023-01-10 \
  --till-date 2023-01-20 \
  --save-raw \
  --save-normalized
```

For futures and currency candles, `--board` may be supplied explicitly. If it
is omitted, the adapter discovers `BOARDID` from current MOEX metadata and uses
the market-level candle endpoint where available.

Futures metadata snapshots:

```bash
uv run moex-iss futures snapshot --save-raw --save-normalized
uv run moex-iss metadata snapshots --data-root data
uv run moex-iss futures search \
  --query CNY \
  --metadata-path <path printed by metadata snapshots>
```

The CLI prints compact summaries: identifiers, requested range, row count,
min/max timestamp, output paths, and quality status.

## Preparing futures data for continuous futures research

Use the adapter to prepare concrete CNY/RUB futures inputs for downstream
research:

```bash
uv run moex-iss futures prepare-chain-data \
  --query CNY \
  --timeframe 1d \
  --from-date 2015-01-01 \
  --till-date 2026-01-01 \
  --save-raw \
  --save-normalized \
  --overwrite
```

The command creates a futures metadata snapshot, discovers matching concrete
contracts from metadata, downloads daily candles per SECID, saves raw JSON and
canonical OHLCV Parquet, runs per-contract quality checks, and prints a compact
summary of downloaded and skipped contracts. It does not stitch contracts, roll
contracts, back-adjust prices, or build a continuous futures series.

Optional filters:

```bash
uv run moex-iss futures prepare-chain-data \
  --query CNY \
  --asset-code CNY \
  --secid-prefix CR \
  --include-secid CRU6 \
  --exclude-secid CNYRUBF \
  --limit 4 \
  --board RFUD \
  --from-date 2023-01-01 \
  --till-date 2023-03-31 \
  --save-raw \
  --save-normalized \
  --overwrite
```

Validate the adapter output in `ohlcv-data-store`:

```bash
cd ../ohlcv-data-store
uv run ohlcv-store validate --data-root ../moex_iss_adapter/data
```

Then inspect and build the continuous chain in `continuous-futures-builder`:

```bash
cd ../continuous-futures-builder
uv run continuous-futures snapshots --data-root ../moex_iss_adapter/data
uv run continuous-futures chain --data-root ../moex_iss_adapter/data --exchange MOEX --engine futures --market forts --metadata-snapshot-ts <SNAPSHOT_TS> --query CNY
```

Continuous futures construction belongs to `continuous-futures-builder`, not to
this adapter.

## Storage Layout

Raw candles are saved without destructive transformation:

```text
data/raw/moex/candles/
  engine=stock/market=shares/board=TQBR/symbol=SBER/timeframe=1d/
    from=2020-01-01_till=2024-12-31.json
```

Normalized candles are saved as Parquet:

```text
data/normalized/candles/
  exchange=MOEX/engine=stock/market=shares/board=TQBR/symbol=SBER/timeframe=1d/
    part-000.parquet
```

Futures and currency candles use the same layout with their own `engine`,
`market`, discovered or supplied `board`, and concrete SECID as `symbol`.

Futures metadata snapshots:

```text
data/raw/moex/metadata/engine=futures/market=forts/securities/
  snapshot_ts=20260704T123045Z.json

data/normalized/metadata/exchange=MOEX/engine=futures/market=forts/securities/
  snapshot_ts=20260704T123045Z/part-000.parquet
```

## Canonical OHLCV Schema

Normalized candle columns:

```text
source
exchange
engine
market
board
symbol
timeframe
ts
open
high
low
close
volume
value
currency
```

The normalized timestamp column is always `ts`. Raw MOEX `begin` is allowed
only in raw response parsing and fixtures. Futures and currency discovery fields
stay in metadata/raw responses and are not added to canonical OHLCV rows.

## Futures Metadata Schema

```text
source
exchange
engine
market
board
secid
shortname
secname
assetcode
instrument_type
last_trade_date
expiration_date
currency
lot_size
raw_metadata
snapshot_ts
```

## Tests

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/unit tests/contract
```

```bash
uv run pytest tests/integration -m integration
```

## Known Limitations

- MOEX ISS only.
- Candles only.
- Primary timeframe: `1d`.
- Futures support concrete expiring contracts only.
- Currency support concrete `currency/selt` instruments only.
- No continuous futures stitching or roll rules.
- No corporate action or dividend adjustment.
- No survivorship-bias-free universe.

## Explicitly Out Of Scope

- Continuous futures construction and back-adjustment.
- Equity universe construction.
- Cross-adapter `data_store` infrastructure.
- Backtesting, strategies, execution, PnL, and portfolio simulation.
- Visualization, web APIs, and database/server orchestration.
