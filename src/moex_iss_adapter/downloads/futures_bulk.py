"""Public compatibility facade for split implementation modules."""

from moex_iss_adapter.downloads._futures_bulk_download import (
    _download_one_bulk_contract as _download_one_bulk_contract,
)
from moex_iss_adapter.downloads._futures_bulk_download import (
    _manual_include_contracts as _manual_include_contracts,
)
from moex_iss_adapter.downloads._futures_bulk_download import _merge_contracts as _merge_contracts
from moex_iss_adapter.downloads._futures_bulk_filters import (
    FUTURES_BULK_QUERY_FIELDS as FUTURES_BULK_QUERY_FIELDS,
)
from moex_iss_adapter.downloads._futures_bulk_filters import _casefold_set as _casefold_set
from moex_iss_adapter.downloads._futures_bulk_filters import _contains as _contains
from moex_iss_adapter.downloads._futures_bulk_filters import (
    _contract_from_row as _contract_from_row,
)
from moex_iss_adapter.downloads._futures_bulk_filters import (
    _contract_sort_key as _contract_sort_key,
)
from moex_iss_adapter.downloads._futures_bulk_filters import _matches_filters as _matches_filters
from moex_iss_adapter.downloads._futures_bulk_filters import _optional_date as _optional_date
from moex_iss_adapter.downloads._futures_bulk_filters import _optional_str as _optional_str
from moex_iss_adapter.downloads._futures_bulk_filters import _parse_user_date as _parse_user_date
from moex_iss_adapter.downloads._futures_bulk_filters import (
    derive_contract_date_range as derive_contract_date_range,
)
from moex_iss_adapter.downloads._futures_bulk_metadata import (
    _fetch_metadata_snapshot as _fetch_metadata_snapshot,
)
from moex_iss_adapter.downloads._futures_bulk_metadata import (
    _load_metadata_snapshot as _load_metadata_snapshot,
)
from moex_iss_adapter.downloads._futures_bulk_metadata import (
    _snapshot_ts_from_frame as _snapshot_ts_from_frame,
)
from moex_iss_adapter.downloads._futures_bulk_metadata import (
    _snapshot_ts_from_path as _snapshot_ts_from_path,
)
from moex_iss_adapter.downloads._futures_bulk_metadata import (
    select_futures_chain_contracts as select_futures_chain_contracts,
)
from moex_iss_adapter.downloads._futures_bulk_runner import (
    format_futures_bulk_summary as format_futures_bulk_summary,
)
from moex_iss_adapter.downloads._futures_bulk_runner import (
    prepare_futures_chain_data as prepare_futures_chain_data,
)
