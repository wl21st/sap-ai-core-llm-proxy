"""Certificate error detection and handling utilities."""

import re

# Pre-compiled regex pattern for certificate error detection
# Covers certificate verify failures, SSL errors, and CA certificate issues
_CERTIFICATE_ERROR_PATTERN = re.compile(
    r"certificate\s*verify\s*failed|"
    r"certificate_verify_failed|"
    r"certificate\s*verification\s*failed|"
    r"ssl.*certificate\s*verify\s*failed|"
    r"sslv3_alert_unknown_ca|"
    r"ssl.*alert.*unknown\s*ca|"
    r"ssl.*alert.*certificate\s*unknown|"
    r"certificate\s*required|"
    r"ca\s*certificate|"
    # botocore.exceptions.SSLError produces "SSL validation failed for <url> ..."
    # This covers network reconnect scenarios where cached SSL connections break.
    r"ssl\s*validation\s*failed",
    re.IGNORECASE,
)

# Pattern matching class names from botocore/urllib3 SSL exception hierarchy.
# botocore.exceptions.SSLError has type name "SSLError" and inherits from OSError,
# but its class name alone is ambiguous. We only match it when the string also
# indicates an SSL context failure (handled by _CERTIFICATE_ERROR_PATTERN above).
_SSL_TYPE_NAME_PATTERN = re.compile(r"^SSLError$", re.IGNORECASE)


def is_certificate_error(error: Exception) -> bool:
    """Check if an exception is related to TLS/SSL certificate verification.

    Certificate errors can occur from OSError with SSL/certificate keywords,
    boto3/botocore SSL errors, or requests SSL errors.

    This also covers network-reconnect scenarios where a cached botocore/urllib3
    connection pool holds a stale SSL context. When WiFi drops and reconnects,
    macOS destroys the OS-level SSL state and subsequent SSL handshakes raise
    ``botocore.exceptions.SSLError`` wrapping a ``FileNotFoundError``. The
    string representation is "SSL validation failed for <url> [Errno 2] No such
    file or directory", which is matched by the ``ssl\\s*validation\\s*failed``
    branch of ``_CERTIFICATE_ERROR_PATTERN``.

    Args:
        error: Exception to check

    Returns:
        True if the error is a certificate verification error, False otherwise
    """
    error_str = str(error)
    error_type_name = type(error).__name__

    return bool(
        _CERTIFICATE_ERROR_PATTERN.search(error_str)
        or _CERTIFICATE_ERROR_PATTERN.search(error_type_name)
    )
