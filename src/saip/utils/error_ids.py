"""
Error ID constants for Sentry tracking and error correlation.

This module defines centralized error IDs for all critical error conditions
in the SAP AI Core LLM Proxy. These IDs enable production debugging, error
frequency tracking, and error correlation across logs.
"""


class ErrorIDs:
    """Centralized error ID constants for logging and Sentry tracking."""

    # Deployment fetch errors
    DEPLOYMENT_FETCH_TIMEOUT = "DEPLOY_FETCH_TIMEOUT"
    DEPLOYMENT_FETCH_NETWORK = "DEPLOY_FETCH_NETWORK"
    DEPLOYMENT_FETCH_AUTH = "DEPLOY_FETCH_AUTH"
    DEPLOYMENT_FETCH_FAILED = "DEPLOY_FETCH_FAILED"

    # Auto-discovery errors
    AUTODISCOVERY_AUTH_FAILED = "AUTODISCOVERY_AUTH"
    AUTODISCOVERY_NETWORK_ERROR = "AUTODISCOVERY_NETWORK"
    AUTODISCOVERY_UNEXPECTED_ERROR = "AUTODISCOVERY_ERROR"

    # Cache errors
    CACHE_PERMISSION_DENIED = "CACHE_PERM_DENIED"
    CACHE_OS_ERROR = "CACHE_OS_ERROR"
    CACHE_STATS_FAILED = "CACHE_STATS_FAILED"

    # Config errors
    INVALID_DEPLOYMENT_ID = "CONFIG_INVALID_ID"
    DEPLOYMENT_NOT_FOUND = "CONFIG_DEPLOY_404"
    DEPLOYMENT_RESOLUTION_FAILED = "CONFIG_RESOLVE_FAILED"

    # Model validation errors
    DEPLOYMENT_METADATA_MISSING = "MODEL_METADATA_MISSING"
    DEPLOYMENT_MODEL_EXTRACTION_FAILED = "MODEL_EXTRACT_FAILED"
    INVALID_URL_FORMAT = "INVALID_URL_FORMAT"
