"""
Custom exception classes for SAP AI Core LLM Proxy.

These exceptions provide specific error handling for different failure scenarios,
enabling proper error propagation and detailed error reporting.
"""


class ProxyException(Exception):
    """Base exception for SAP AI Core LLM Proxy."""

    pass


class CacheError(ProxyException):
    """Raised when cache operations fail."""

    pass


class DeploymentFetchError(ProxyException):
    """Raised when deployment fetching fails.

    This includes network errors, authentication failures, timeouts,
    and other deployment discovery issues.
    """

    pass


class DeploymentResolutionError(ProxyException):
    """Raised when deployment ID resolution to URL fails.

    This includes invalid deployment IDs, missing deployments,
    and permission issues during resolution.
    """

    pass


class ConfigValidationError(ProxyException):
    """Raised when configuration validation fails.

    This includes invalid service keys, bad credentials,
    and configuration parsing errors.
    """

    pass


class AuthenticationError(ProxyException):
    """Raised when authentication with SAP AI Core fails.

    This includes invalid credentials, expired tokens,
    and permission denied errors.
    """

    pass
