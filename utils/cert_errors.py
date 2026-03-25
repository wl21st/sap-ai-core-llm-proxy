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
    r"ca\s*certificate",
    re.IGNORECASE,
)


def is_certificate_error(error: Exception) -> bool:
    """Check if an exception is related to TLS/SSL certificate verification.

    Certificate errors can occur from OSError with SSL/certificate keywords,
    boto3/botocore SSL errors, or requests SSL errors.

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
