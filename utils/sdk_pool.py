import threading
from logging import Logger

from botocore.config import Config
from gen_ai_hub.proxy import get_proxy_client
from gen_ai_hub.proxy.core.base import BaseProxyClient
from gen_ai_hub.proxy.native.amazon.clients import ClientWrapper, Session

from config import ServiceKey, SubAccountConfig
from utils import logging_utils

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

logger: Logger = logging_utils.get_server_logger(__name__)


def __get_sdk_session() -> Session:
    """Lazily initialize and return a global SAP AI Core SDK Session.

    Returns:
        Session configured for SAP AI Core
    """
    global __sdk_session
    if __sdk_session is None:
        with __session_lock:
            if __sdk_session is None:
                logger.info("Initializing global SAP AI SDK Session")
                # Session() handles AWS-style authentication for Bedrock models via SAP AI Core
                __sdk_session = Session()
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
    sub_account_config: SubAccountConfig, model_name: str, deployment_id: str
) -> ClientWrapper:
    """Get or create a cached SAP AI Core (Bedrock) client for the given model_name or deployment_id.

    Args:
        sub_account_config: SubAccount configuration containing service key credentials
        model_name: Model name for caching purposes
        deployment_id: SAP AI Core deployment ID

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
            )

            # Get the session and proxy client
            sdk_session: Session = __get_sdk_session()
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


def invalidate_bedrock_client(model_name: str) -> None:
    """Invalidate the cached Bedrock client for a given model.

    This removes the client from the cache, forcing a new client to be created
    on the next request. Should be called when authentication errors (401/403)
    occur, indicating the cached credentials may be invalid.

    Args:
        model_name: Model name whose client should be invalidated
    """
    global __model_client_map, __proxy_client

    with __clients_lock:
        if model_name in __model_client_map:
            logger.info(f"Invalidating cached Bedrock client for model '{model_name}'")
            del __model_client_map[model_name]

    # Also invalidate the proxy client to force re-authentication.
    # The proxy client holds authentication state at the subaccount level,
    # so invalidating it ensures all models under this subaccount will
    # use fresh credentials on their next request.
    with __session_lock:
        if __proxy_client is not None:
            logger.info("Invalidating global SAP AI Core proxy client")
            __proxy_client = None
