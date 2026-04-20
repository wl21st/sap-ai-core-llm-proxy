"""
CA certificate bundle resolution utilities.

Provides a multi-level fallback chain to locate a valid CA bundle for TLS
verification, independent of the Bedrock SDK.
"""

import os
import ssl
from logging import Logger
from pathlib import Path

from utils import logging_utils
from utils.exceptions import ConfigValidationError

logger: Logger = logging_utils.get_server_logger(__name__)


def resolve_ca_cert_bundle(configured_path: str | None) -> str | None:
    """Resolve the TLS CA certificate bundle path using a multi-level fallback chain.

    Order:
    1. Use configured path if specified and valid
    2. Try certifi.where() (Python's default CA bundle)
    3. Check system paths by OS
    4. Use ssl.get_default_verify_paths()
    5. Return None to let SDK/requests use their defaults

    Args:
        configured_path: Optional path to CA certificate bundle from config

    Returns:
        Path to CA certificate bundle as string, or None

    Raises:
        ConfigValidationError: If configured_path is specified but invalid
    """
    if configured_path:
        path = Path(configured_path)
        if not path.exists():
            raise ConfigValidationError(
                f"Configured ca_cert_bundle path does not exist: {configured_path}"
            )
        if not path.is_file():
            raise ConfigValidationError(
                f"Configured ca_cert_bundle path is not a file: {configured_path}"
            )
        if not os.access(path, os.R_OK):
            raise ConfigValidationError(
                f"Configured ca_cert_bundle path is not readable: {configured_path}"
            )
        logger.info("Using configured CA certificate bundle: %s", configured_path)
        return str(path)

    # Try certifi
    try:
        import certifi

        cert_path = certifi.where()
        if cert_path and Path(cert_path).exists():
            logger.info("Using certifi CA certificate bundle: %s", cert_path)
            return cert_path
    except ImportError:
        logger.debug("certifi not available, trying alternative paths")
    except Exception as e:
        logger.debug("certifi.where() failed: %s, trying alternative paths", e)

    # System paths by OS
    system_cert_paths: list[str] = []
    if os.name == "posix":
        system_cert_paths = [
            "/etc/ssl/certs/ca-bundle.crt",
            "/etc/ssl/certs/ca-certificates.crt",
            "/etc/pki/tls/certs/ca-bundle.crt",
            "/usr/local/etc/openssl/cert.pem",
            "/etc/ssl/cert.pem",
        ]
    elif os.name == "nt":
        system_cert_paths = [
            os.path.expandvars(r"%ALLUSERSPROFILE%\ssl\certs\ca-bundle.crt"),
            os.path.expandvars(r"%ALLUSERSPROFILE%\ssl\certs\ca-certificates.crt"),
        ]

    for path_str in system_cert_paths:
        path = Path(path_str)
        if path.exists() and path.is_file() and os.access(path, os.R_OK):
            logger.info("Found CA certificate bundle at system path: %s", path_str)
            return str(path)

    # ssl module fallback
    try:
        verify_paths = ssl.get_default_verify_paths()
        if verify_paths.cafile and Path(verify_paths.cafile).exists():
            logger.info("Using ssl module default CA bundle: %s", verify_paths.cafile)
            return verify_paths.cafile
        if verify_paths.capath and Path(verify_paths.capath).exists():
            logger.info("Using ssl module default CA path: %s", verify_paths.capath)
            return verify_paths.capath
    except Exception as e:
        logger.debug("ssl.get_default_verify_paths() failed: %s", e)

    logger.warning(
        "Could not locate CA certificate bundle. SDK/requests will use their defaults. "
        "If TLS verification fails, set ca_cert_bundle in config or install certifi."
    )
    return None
