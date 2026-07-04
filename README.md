# moex_iss_adapter

`moex_iss_adapter` is a standalone adapter for fetching MOEX ISS candle data,
preserving raw responses, normalizing candles to one canonical OHLCV schema,
saving normalized data as Parquet, and running adapter-level quality checks.

## Supported MVP Scope

- Source: MOEX ISS only.
- Data type: candles only.
- Primary validation scenario: `stock` / `shares` / `TQBR` / `SBER` / `1d`.
- Futures discovery and candles: `futures` / `forts` for concrete futures
  contract SECIDs.
- Currency discovery and candles: `currency` / `selt` for concrete currency
  SECIDs.
- Storage: local files under `data/raw` and `data/normalized`.

The adapter is not a backtest engine and does not contain strategies, order
simulation, portfolio accounting, visualization, a web API, or database/server
infrastructure.

## Setup

```bash
uv sync --extra dev
```

If using pip directly:

```bash
python -m pip install -e ".[dev]"
```

## Official MOEX ISS Sources

Local source notes live in `docs/moex_iss/sources.md`.

- Official ISS reference: https://iss.moex.com/iss/reference/
- Official MOEX ISS developer manual: https://www.moex.com/en/documents/8888
- Official ISS service description: https://www.moex.com/a2920

The MVP endpoint registry is documented in
`docs/moex_iss/endpoint_registry.yaml`.

## Snapshot Script

Small MOEX ISS samples can be refreshed with:

```bash
uv run python scripts/snapshot_moex_iss.py
```

The script fetches only small deterministic samples: engines, stock markets,
stock/shares boards, ISS durations, SBER/TQBR daily candles for `2023-01-10`
through `2023-01-20`, futures/forts boards, futures securities columns, a small
futures securities sample, and a small futures candle sample when a suitable
contract is available. Checked-in tests use minimal fixtures that match the
MOEX ISS `columns` plus `data` response shape, so default tests do not require
network access.

## CLI Usage

Stock/share candle download:

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

The CLI prints a compact summary: symbol, board, timeframe, requested range,
row count, min/max timestamp, raw path, normalized path, and quality status.

Futures discovery:

```bash
uv run moex-iss futures search --query CNY
```

The search output is compact and includes `SECID`, `SHORTNAME`, `SECNAME`,
`BOARDID`, `ASSETCODE`, and last trade date when MOEX provides them.

Futures candle download for one concrete discovered SECID:

```bash
uv run moex-iss futures candles \
  --symbol CNYRUBF \
  --timeframe 1d \
  --from-date 2023-01-10 \
  --till-date 2023-01-20 \
  --save-raw \
  --save-normalized
```

`--board` may be supplied explicitly, for example `--board RFUD`. If omitted,
the adapter discovers the board from MOEX futures securities metadata and uses
the market-level candle endpoint where available.

Currency discovery:

```bash
uv run moex-iss currency search --query CNY
uv run moex-iss currency search --query USD
uv run moex-iss currency search --query RUB
```

Currency SECIDs can differ from intuitive pair names, so discover the concrete
instrument first and then download candles for that SECID.

Currency candle download:

```bash
uv run moex-iss currency candles \
  --symbol <DISCOVERED_CURRENCY_SECID> \
  --timeframe 1d \
  --from-date 2023-01-10 \
  --till-date 2023-01-20 \
  --save-raw \
  --save-normalized
```

`--board` may be supplied explicitly, for example `--board CETS`. If omitted,
the adapter discovers the board from MOEX currency securities metadata and uses
the market-level candle endpoint where available.

Futures metadata snapshot:

```bash
uv run moex-iss futures snapshot \
  --save-raw \
  --save-normalized
```

List saved normalized metadata snapshots:

```bash
uv run moex-iss metadata snapshots --data-root data
```

Filter the list to futures/FORTS snapshots:

```bash
uv run moex-iss metadata snapshots \
  --engine futures \
  --market forts
```

Search from a saved normalized metadata snapshot instead of live MOEX ISS:

```bash
uv run moex-iss futures search \
  --query CNY \
  --metadata-path <path printed by metadata snapshots>
```

Saved metadata search supports `--query`, `--secid`, `--short-name`,
`--security-name`, and `--asset-code`.

## Storage Layout

Raw MOEX responses are saved without destructive transformation:

```text
data/
  raw/
    moex/
      candles/
        engine=stock/
          market=shares/
            board=TQBR/
              symbol=SBER/
                timeframe=1d/
                  from=2020-01-01_till=2024-12-31.json
```

Normalized candles are saved as Parquet:

```text
data/
  normalized/
    candles/
      exchange=MOEX/
        engine=stock/
          market=shares/
            board=TQBR/
              symbol=SBER/
                timeframe=1d/
                  part-000.parquet
```

Futures candles use the same storage layout with `engine=futures`,
`market=forts`, the discovered or supplied futures board, and the concrete
futures SECID as `symbol`.

Currency candles use the same storage layout with `engine=currency`,
`market=selt`, the discovered or supplied currency board, and the concrete
currency SECID as `symbol`.

Raw futures metadata snapshots are saved separately:

```text
data/
  raw/
    moex/
      metadata/
        engine=futures/
          market=forts/
            securities/
              snapshot_ts=20260704T123045Z.json
```

Normalized futures metadata snapshots are saved as Parquet:

```text
data/
  normalized/
    metadata/
      exchange=MOEX/
        engine=futures/
          market=forts/
            securities/
              snapshot_ts=20260704T123045Z/
                part-000.parquet
```

## Canonical OHLCV Schema

Normalized candle data always uses this exact column order:

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

The normalized timestamp column is `ts`. Raw MOEX `begin` is allowed only in raw
response parsing and fixtures.

Futures metadata such as `ASSETCODE`, `SHORTNAME`, `SECNAME`, `LASTTRADEDATE`,
and `LASTDELDATE` is discovery metadata. It is not added to the canonical OHLCV
schema.

Currency metadata such as `FACEUNIT`, `CURRENCYID`, `LOTSIZE`, and `SETTLEDATE`
is discovery metadata or raw-response data. It is not added to the canonical
OHLCV schema.

## Futures Metadata Schema

Normalized futures metadata uses this stable schema:

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

`snapshot_ts` records when the metadata snapshot was created. `raw_metadata`
contains the original MOEX row as JSON text for reproducibility.

## Tests

Default tests do not require network access:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/unit tests/contract
```

Integration tests are isolated behind a marker:

```bash
uv run pytest tests/integration -m integration
```

## Known MVP Limitations

- MOEX ISS only.
- Candles only.
- Primary scenario: `stock` / `shares` / `TQBR`.
- Primary validation symbol: `SBER`.
- Primary timeframe: `1d`.
- Futures support downloads concrete expiring futures contracts only.
- Currency support downloads concrete `currency/selt` instruments only.
- No continuous futures stitching.
- No back-adjusted futures series.
- No futures roll rules.
- No open interest analytics.
- No futures margin or settlement modeling.
- No corporate actions.
- No dividend adjustment.
- No survivorship-bias-free universe.
- No backtest engine.
- No visualization layer.
- No web API.
