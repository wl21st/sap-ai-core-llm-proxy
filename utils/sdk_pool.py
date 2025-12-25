import threading
from logging import Logger

from botocore.config import Config
from gen_ai_hub.proxy.native.amazon.clients import ClientWrapper, Session

from utils import logging_utils

# ------------------------
# SAP AI SDK session/client cache for performance
# ------------------------
# Creating a new SDK Session()/client per request is expensive. Reuse a process-wide
# Session and cache clients per model in a thread-safe manner.
__session_lock = threading.Lock()
__clients_lock = threading.Lock()

__sdk_session = None
__model_client_map: dict[str, ClientWrapper] = {}

logger: Logger = logging_utils.get_server_logger(__name__)


def __get_sdk_session() -> Session:
    """Lazily initialize and return a global SAP AI Core SDK Session."""
    global __sdk_session
    if __sdk_session is None:
        with __session_lock:
            if __sdk_session is None:
                logger.info("Initializing global SAP AI SDK Session")
                __sdk_session = Session()
    return __sdk_session


def get_bedrock_client(model_name: str, deployment_id: str) -> ClientWrapper:
    """Get or create a cached SAP AI Core (Bedrock) client for the given model_name or deployment_id."""
    bedrock_client: ClientWrapper = __model_client_map.get(model_name)

    if bedrock_client is not None:
        return bedrock_client

    with __clients_lock:
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

            sdk_session: Session = __get_sdk_session()

            bedrock_client = sdk_session.client(
                deployment_id=deployment_id,
                config=client_config
            )
            __model_client_map[model_name] = bedrock_client

    return bedrock_client
