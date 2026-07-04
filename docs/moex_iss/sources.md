# MOEX ISS Sources

Updated: 2026-07-04

## Official Sources

- Official ISS reference: https://iss.moex.com/iss/reference/
- Official MOEX ISS developer manual: https://www.moex.com/en/documents/8888
- Official ISS service description: https://www.moex.com/a2920

## MVP Endpoints

- Base URL: https://iss.moex.com/iss
- ISS reference: https://iss.moex.com/iss/reference/
- Engines: https://iss.moex.com/iss/engines.json
- Markets for stock: https://iss.moex.com/iss/engines/stock/markets.json
- Boards for stock/shares:
  https://iss.moex.com/iss/engines/stock/markets/shares/boards.json
- Board-specific SBER candles:
  https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/SBER/candles.json?from=2023-01-10&till=2023-01-20&interval=24&start=0
- Futures securities:
  https://iss.moex.com/iss/engines/futures/markets/forts/securities.json
- Futures securities columns:
  https://iss.moex.com/iss/engines/futures/markets/forts/securities/columns.json
- Futures boards:
  https://iss.moex.com/iss/engines/futures/markets/forts/boards.json
- Futures market-level candles:
  https://iss.moex.com/iss/engines/futures/markets/forts/securities/CNYRUBF/candles.json?from=2023-01-10&till=2023-01-20&interval=24&start=0
- Futures board-specific candles:
  https://iss.moex.com/iss/engines/futures/markets/forts/boards/RFUD/securities/CNYRUBF/candles.json?from=2023-01-10&till=2023-01-20&interval=24&start=0
- Currency securities:
  https://iss.moex.com/iss/engines/currency/markets/selt/securities.json
- Currency securities columns:
  https://iss.moex.com/iss/engines/currency/markets/selt/securities/columns.json
- Currency boards:
  https://iss.moex.com/iss/engines/currency/markets/selt/boards.json
- Currency market-level candles:
  https://iss.moex.com/iss/engines/currency/markets/selt/securities/CNY000000TOD/candles.json?from=2023-01-10&till=2023-01-20&interval=24&start=0
- Currency board-specific candles:
  https://iss.moex.com/iss/engines/currency/markets/selt/boards/CETS/securities/CNY000000TOD/candles.json?from=2023-01-10&till=2023-01-20&interval=24&start=0

## Interval Notes

The adapter uses the MOEX ISS candle interval values exposed by the ISS
durations dictionary and reflected by the official candle endpoint examples:

```text
1m  -> 1
10m -> 10
1h  -> 60
1d  -> 24
1w  -> 7
1mo -> 31
1q  -> 4
```

Refresh the local API snapshots with `scripts/snapshot_moex_iss.py` when network
access to MOEX ISS is available. The script does not copy full MOEX
documentation into this repository. The script also writes a raw futures
securities metadata snapshot and a normalized futures metadata Parquet snapshot
under `docs/moex_iss/snapshots/`.

## Futures Notes

Futures support is limited to discovery and candle download for concrete MOEX
futures contract symbols under `engine=futures` and `market=forts`. Futures
contracts expire, so active SECIDs change over time. The adapter does not build
continuous futures, back-adjusted series, roll rules, margin models, settlement
models, or futures analytics.

## Currency Notes

Currency support is limited to discovery and candle download for concrete MOEX
currency SECIDs under `engine=currency` and `market=selt`. Users should discover
the concrete instrument first because SECIDs such as CNY/RUB and USD/RUB may not
match intuitive names.
