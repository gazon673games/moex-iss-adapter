# Adapter Scope

`moex_iss_adapter` is a standalone MOEX ISS adapter. Its boundary is the data
extraction path:

```text
MOEX ISS API -> raw JSON -> normalized Parquet -> metadata snapshots -> quality reports
```

## What It Does

- Builds MOEX ISS endpoint requests.
- Downloads paginated candle and metadata responses.
- Preserves raw JSON responses.
- Normalizes OHLCV candles to the canonical schema.
- Saves normalized candles and futures metadata as Parquet.
- Runs structured quality checks.
- Exposes adapter operations through a compact CLI.

## What It Does Not Do

- Backtests, strategies, signal generation, PnL, or portfolio simulation.
- Visualization, dashboards, web APIs, or database server infrastructure.
- Continuous futures, roll rules, or back-adjusted futures series.
- Equity universe construction or survivorship-bias-free datasets.
- A cross-source `data_store`.

## Why Continuous Futures Stay Out

Continuous futures are derived research data. Building them requires contract
selection, roll schedules, adjustment rules, and policy choices that are not
part of raw market-data extraction. This adapter can provide concrete futures
contracts and metadata snapshots as inputs, but stitching belongs in a separate
future module.

## Why Equity Universes Stay Out

An equity universe needs membership rules, historical listings, delistings,
liquidity filters, and survivorship-bias controls. Those are research dataset
decisions. The adapter can download candles and raw metadata ingredients, but a
universe builder should live outside this repository.

## Why `data_store` Stays Separate

A `data_store` would coordinate storage policies across adapters and consumers.
That is an application/platform concern. This repository only writes local raw
and normalized artifacts for MOEX ISS in deterministic paths.
