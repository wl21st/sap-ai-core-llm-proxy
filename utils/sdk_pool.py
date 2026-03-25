import os
import ssl
import threading
from logging import Logger
from pathlib import Path

from botocore.config import Config
from gen_ai_hub.proxy import get_proxy_client
from gen_ai_hub.proxy.core.base import BaseProxyClient
from gen_ai_hub.proxy.native.amazon.clients import ClientWrapper, Session

from config import ServiceKey, SubAccountConfig
from utils import logging_utils
from utils.exceptions import ConfigValidationError

# ------------------------
# SAP AI SDK session/client cache for performance
# ------------------------
# Creating a new SDK Session()/client per request is expensive. Reuse a process-wide
# Session and cache clients per model in a thread-safe manner.
__session_lock = threading.Lock()
__clients_lock = threading.Lock()

__sdk_session: Session | None = None
__proxy_client: BaseProxyClient | None = None
__model_client_map: dict[str, ClientWrapper] = {}
__current_ca_cert_bundle: str | None = (
    None  # Track the currently configured certificate
)

logger: Logger = logging_utils.get_server_logger(__name__)


def resolve_ca_cert_bundle(configured_path: str | None) -> str | None:
    """Resolve the TLS CA certificate bundle path using a multi-level fallback chain.

    This function attempts to locate a valid CA certificate bundle for TLS verification,
    following this order:
    1. Use configured path if specified and valid
    2. Try certifi.where() (Python's default CA bundle)
    3. Check system paths by OS (/etc/ssl/certs/ca-bundle.crt on Linux, etc.)
    4. Use ssl.get_default_verify_paths()
    5. Return None to let SDK/requests use their defaults

    Args:
        configured_path: Optional path to CA certificate bundle from config

    Returns:
        Path to CA certificate bundle as string, or None if none found (SDK will use defaults)

    Raises:
        ConfigValidationError: If configured_path is specified but invalid
    """
    # If path is configured, validate and use it
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
        logger.info(f"Using configured CA certificate bundle: {configured_path}")
        return str(path)

    # Try certifi (Python standard CA bundle)
    try:
        import certifi

        cert_path = certifi.where()
        if cert_path and Path(cert_path).exists():
            logger.info(f"Using certifi CA certificate bundle: {cert_path}")
            return cert_path
    except ImportError:
        logger.debug("certifi not available, trying alternative paths")
    except Exception as e:
        logger.debug(f"certifi.where() failed: {e}, trying alternative paths")

    # Try system paths by OS
    system_cert_paths = []
    if os.name == "posix":  # Unix-like systems (Linux, macOS)
        system_cert_paths = [
            "/etc/ssl/certs/ca-bundle.crt",  # Linux (CentOS, Fedora, RHEL)
            "/etc/ssl/certs/ca-certificates.crt",  # Linux (Debian, Ubuntu)
            "/etc/pki/tls/certs/ca-bundle.crt",  # Linux (older distributions)
            "/usr/local/etc/openssl/cert.pem",  # macOS
            "/etc/ssl/cert.pem",  # macOS (alternative)
            "/usr/local/share/ca-certificates/",  # Linux (alternative)
        ]
    elif os.name == "nt":  # Windows
        system_cert_paths = [
            os.path.expandvars(r"%ALLUSERSPROFILE%\ssl\certs\ca-bundle.crt"),
            os.path.expandvars(r"%ALLUSERSPROFILE%\ssl\certs\ca-certificates.crt"),
        ]

    for path_str in system_cert_paths:
        path = Path(path_str)
        if path.exists() and path.is_file() and os.access(path, os.R_OK):
            logger.info(f"Found CA certificate bundle at system path: {path_str}")
            return str(path)

    # Try ssl.get_default_verify_paths() as last fallback
    try:
        verify_paths = ssl.get_default_verify_paths()
        if verify_paths.cafile and Path(verify_paths.cafile).exists():
            logger.info(f"Using ssl module default CA bundle: {verify_paths.cafile}")
            return verify_paths.cafile
        if verify_paths.capath and Path(verify_paths.capath).exists():
            logger.info(f"Using ssl module default CA path: {verify_paths.capath}")
            return verify_paths.capath
    except Exception as e:
        logger.debug(f"ssl.get_default_verify_paths() failed: {e}")

    # No bundle found, log warning and let SDK use its own defaults
    logger.warning(
        "Could not locate CA certificate bundle. SDK/requests will use their defaults. "
        "If TLS verification fails, set ca_cert_bundle in config or install certifi."
    )
    return None


def __get_sdk_session(ca_cert_bundle: str | None = None) -> Session:
    """Lazily initialize and return a global SAP AI Core SDK Session.

    Args:
        ca_cert_bundle: Optional path to CA certificate bundle for TLS verification.
            If provided, sets environment variables for boto3/botocore to use.
            If the certificate bundle changes from what was previously set, the session
            will be invalidated and recreated with the new certificate.

    Returns:
        Session configured for SAP AI Core

    Note:
        This function handles certificate bundle changes by detecting when the requested
        certificate differs from the currently active one. If a change is detected,
        it invalidates the existing session and creates a new one with the new certificate.
        This prevents stale certificate caching when configuration is updated.
    """
    global __sdk_session, __current_ca_cert_bundle

    # Check if certificate bundle has changed (requires session reset)
    if __current_ca_cert_bundle != ca_cert_bundle:
        with __session_lock:
            # Double-check under lock to prevent race conditions
            if __current_ca_cert_bundle != ca_cert_bundle:
                if __sdk_session is not None:
                    logger.warning(
                        f"Certificate bundle changed from '{__current_ca_cert_bundle}' to '{ca_cert_bundle}'. "
                        "Invalidating SDK session to apply new certificate."
                    )
                    __sdk_session = None
                    # Clean up old certificate from environment
                    if "AWS_CA_BUNDLE" in os.environ:
                        del os.environ["AWS_CA_BUNDLE"]

    # Initialize session if not already done
    if __sdk_session is None:
        with __session_lock:
            if __sdk_session is None:
                logger.info("Initializing global SAP AI SDK Session")

                # If CA certificate bundle is provided, configure it for boto3/botocore
                if ca_cert_bundle:
                    # boto3 respects AWS_CA_BUNDLE environment variable for SSL verification
                    os.environ["AWS_CA_BUNDLE"] = ca_cert_bundle
                    logger.info(f"Set AWS_CA_BUNDLE to: {ca_cert_bundle}")

                # Session() handles AWS-style authentication for Bedrock models via SAP AI Core
                __sdk_session = Session()
                __current_ca_cert_bundle = ca_cert_bundle
    return __sdk_session


def __get_proxy_client(sub_account_config: SubAccountConfig) -> BaseProxyClient:
    """Lazily initialize and return a global SAP AI Core proxy client.

    Args:
        sub_account_config: SubAccount configuration containing service key credentials

    Returns:
        BaseProxyClient configured with SAP AI Core authentication
    """
    global __proxy_client
    if __proxy_client is None:
        with __session_lock:
            if __proxy_client is None:
                logger.info("Initializing SAP AI Core proxy client")
                service_key: ServiceKey | None = sub_account_config.service_key

                if service_key is None:
                    raise ValueError(
                        "Service key is required for SAP AI Core authentication"
                    )

                __proxy_client = get_proxy_client(
                    proxy_version="gen-ai-hub",
                    base_url=service_key.api_url,
                    auth_url=service_key.auth_url,
                    client_id=service_key.client_id,
                    client_secret=service_key.client_secret,
                    resource_group=sub_account_config.resource_group,
                )
                logger.info("SAP AI Core proxy client initialized successfully")
    return __proxy_client


def get_bedrock_client(
    sub_account_config: SubAccountConfig,
    model_name: str,
    deployment_id: str,
    ca_cert_bundle: str | None = None,
) -> ClientWrapper:
    """Get or create a cached SAP AI Core (Bedrock) client for the given model_name or deployment_id.

    Args:
        sub_account_config: SubAccount configuration containing service key credentials
        model_name: Model name for caching purposes
        deployment_id: SAP AI Core deployment ID
        ca_cert_bundle: Optional path to CA certificate bundle for TLS verification

    Returns:
        ClientWrapper configured for the specified deployment
    """
    bedrock_client: ClientWrapper | None = __model_client_map.get(model_name)

    if bedrock_client is not None:
        return bedrock_client

    with __clients_lock:
        # Double-check pattern: verify cache miss again under lock
        bedrock_client = __model_client_map.get(model_name)
        if bedrock_client is None:
            logger.info(f"Creating SAP AI SDK client for model '{model_name}'")
            # Configure client with minimal retries since we handle retries at application level
            client_config = Config(
                retries={
                    "max_attempts": 1,  # Disable botocore retries, let tenacity handle it
                    "mode": "standard",
                },
                max_pool_connections=50,
                tcp_keepalive=True,
                read_timeout=180,  # 180 seconds for long-running LLM requests
            )

            # Get the session and proxy client
            # Pass ca_cert_bundle to session initialization for SDK/boto3 configuration
            sdk_session: Session = __get_sdk_session(ca_cert_bundle)
            proxy_client: BaseProxyClient = __get_proxy_client(sub_account_config)

            # Create the client with authentication via proxy_client
            bedrock_client = sdk_session.client(
                deployment_id=deployment_id,
                config=client_config,
                proxy_client=proxy_client,
            )
            __model_client_map[model_name] = bedrock_client
            logger.info(
                f"SAP AI SDK client created successfully for model '{model_name}'"
            )

    # Type narrowing: bedrock_client is guaranteed non-None here
    assert bedrock_client is not None, (
        "bedrock_client should never be None at this point"
    )
    return bedrock_client


def invalidate_bedrock_client(model_name: str, invalidate_session: bool = True) -> None:
    """Invalidate the cached Bedrock client for a given model.

    This removes the client from the cache, forcing a new client to be created
    on the next request. Optionally invalidates the SDK session and proxy client.

    Args:
        model_name: Model name whose client should be invalidated
        invalidate_session: Whether to also invalidate the SDK session and proxy client.
            Set to False for authentication errors (401/403) where only client/proxy
            invalidation is needed. Set to True for certificate errors where full
            session reset is required.
    """
    global __model_client_map, __proxy_client, __sdk_session, __current_ca_cert_bundle

    with __clients_lock:
        if model_name in __model_client_map:
            logger.info(f"Invalidating cached Bedrock client for model '{model_name}'")
            del __model_client_map[model_name]

    # Also invalidate the proxy client to force re-authentication.
    # The proxy client holds authentication state at the subaccount level,
    # so invalidating it ensures all models under this subaccount will
    # use fresh credentials on their next request.
    if invalidate_session:
        with __session_lock:
            if __proxy_client is not None:
                logger.info("Invalidating global SAP AI Core proxy client")
                __proxy_client = None

            # Also invalidate the SDK session to ensure certificate updates are picked up.
            # The session caches the certificate configuration, so invalidating it
            # forces a fresh session with the current certificate on next use.
            # This is critical for handling certificate rotation/expiry scenarios.
            if __sdk_session is not None:
                logger.info(
                    "Invalidating global SDK session to force fresh certificate handling"
                )
                # Clean up AWS_CA_BUNDLE environment variable when invalidating session
                if "AWS_CA_BUNDLE" in os.environ:
                    del os.environ["AWS_CA_BUNDLE"]
                    logger.info("Cleaned up AWS_CA_BUNDLE environment variable")
                __sdk_session = None
                __current_ca_cert_bundle = None
    else:
        # For auth errors, only invalidate proxy client (not session) to avoid
        # expensive session recreation for all models
        with __session_lock:
            if __proxy_client is not None:
                logger.info("Invalidating global SAP AI Core proxy client (auth error)")
                __proxy_client = None
