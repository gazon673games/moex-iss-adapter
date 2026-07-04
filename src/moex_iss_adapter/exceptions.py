"""Adapter-specific exception hierarchy."""


class MoexIssAdapterError(Exception):
    """Base class for adapter-level failures."""


class MoexHttpError(MoexIssAdapterError):
    """HTTP request or response error."""


class MoexResponseFormatError(MoexIssAdapterError):
    """Unexpected MOEX ISS response shape."""


class MoexEmptyDataError(MoexIssAdapterError):
    """No candle rows were returned for a requested range."""


class MoexNormalizationError(MoexIssAdapterError):
    """Normalization failed."""


class MoexStorageError(MoexIssAdapterError):
    """Raw or normalized storage failed."""


class MoexQualityError(MoexIssAdapterError):
    """Data quality validation failed."""


class MoexPaginationError(MoexIssAdapterError):
    """Pagination did not terminate within configured limits."""
