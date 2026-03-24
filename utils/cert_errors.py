"""Certificate error detection and handling utilities."""


def is_certificate_error(error: Exception) -> bool:
    """Check if an exception is related to TLS/SSL certificate verification.

    Certificate errors can occur from OSError with SSL/certificate keywords,
    boto3/botocore SSL errors, or requests SSL errors.

    Args:
        error: Exception to check

    Returns:
        True if the error is a certificate verification error, False otherwise
    """
    error_str = str(error).lower()
    error_type_name = type(error).__name__.lower()

    cert_keywords = [
        "certificate",
        "ssl",
        "verify",
        "ca certificate",
        "certificate verify failed",
        "sslerror",
        "sslcertificateerror",
    ]

    return any(
        keyword in error_str or keyword in error_type_name for keyword in cert_keywords
    )
