"""Public compatibility facade for split implementation modules."""

from moex_iss_adapter.cli._futures_candles import futures_candles as futures_candles
from moex_iss_adapter.cli._futures_core import (
    _print_prepare_chain_data_result as _print_prepare_chain_data_result,
)
from moex_iss_adapter.cli._futures_core import futures_app as futures_app
from moex_iss_adapter.cli._futures_core import futures_coverage_report as futures_coverage_report
from moex_iss_adapter.cli._futures_prepare import (
    futures_prepare_chain_data as futures_prepare_chain_data,
)
from moex_iss_adapter.cli._futures_search import futures_search as futures_search
from moex_iss_adapter.cli._futures_search import futures_snapshot as futures_snapshot
from moex_iss_adapter.downloads.futures import (
    download_futures_candles as download_futures_candles,
)
from moex_iss_adapter.downloads.futures import (
    search_futures_securities as search_futures_securities,
)
from moex_iss_adapter.downloads.futures_bulk import (
    prepare_futures_chain_data as prepare_futures_chain_data,
)
from moex_iss_adapter.downloads.futures_history import (
    search_historical_futures_contracts as search_historical_futures_contracts,
)
from moex_iss_adapter.downloads.futures_metadata import (
    save_futures_metadata_snapshot as save_futures_metadata_snapshot,
)
