class FeatureSqlToolError(Exception):
    """Base package exception."""


class SqlLoadError(FeatureSqlToolError):
    """Raised when SQL file loading fails."""


class SqlParseError(FeatureSqlToolError):
    """Raised when SQL parsing fails."""


class FeatureResolutionError(FeatureSqlToolError):
    """Raised when a feature dependency cannot be resolved."""
