import hashlib
import logging
import os
from urllib.parse import urlparse

from ai_api_client_sdk.ai_api_v2_client import AIAPIV2Client
from diskcache import Cache

from config.config_models import ServiceKey

logger = logging.getLogger(__name__)

# Cache configuration
CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), ".cache", "deployments"
)
CACHE_DURATION = 7 * 24 * 60 * 60  # 7 days in seconds


def extract_deployment_id(deployment_url: str) -> str:
    """
    Extract deployment ID from SAP AI Core deployment URL.

    Args:
        deployment_url: Full deployment URL (e.g., "https://api.ai.prod.eu-central-1.aws.ml.hana.ondemand.com/v2/inference/deployments/{deployment_id}")

    Returns:
        Deployment ID string if found

    Raises:
        ValueError: If URL format is invalid, empty, or missing deployment ID
    """
    from utils.error_ids import ErrorIDs

    if not deployment_url or not isinstance(deployment_url, str):
        from utils.exceptions import DeploymentResolutionError

        raise DeploymentResolutionError("URL must be a non-empty string")

    try:
        parsed = urlparse(deployment_url)
        path = parsed.path.rstrip("/")  # Remove trailing slash if present

        # Expected pattern: /v2/inference/deployments/{deployment_id}
        if "/deployments/" in path:
            deployment_id = path.split("/deployments/")[-1].split("/")[0]

            if deployment_id:
                return deployment_id.strip()

        raise ValueError(f"No deployment_id in URL: {deployment_url}")
    except ValueError:
        # Re-raise ValueError as-is
        raise
    except Exception as e:
        from utils.exceptions import DeploymentResolutionError

        raise DeploymentResolutionError(f"Failed to parse URL: {e}") from e


def fetch_deployment_url(
    service_key: ServiceKey, deployment_id: str, resource_group: str = "default"
) -> str:
    """Fetch deployment URL from SAP AI Core using the SDK.

    Args:
        service_key: SAP AI Core service key credentials
        deployment_id: Deployment ID to look up
        resource_group: Resource group for the deployment, defaults to "default"

    Returns:
        Full deployment URL

    Raises:
        Exception: If deployment lookup fails (network error, auth error, deployment not found, etc.)
    """
    logger.info(
        f"Fetching deployment URL for ID: {deployment_id} in resource group: {resource_group}"
    )

    try:
        # Create AICoreV2Client with service key credentials
        client = AICoreV2Client(
            base_url=service_key.api_url + "/v2/lm",
            auth_url=service_key.auth_url + "/oauth/token",
            client_id=service_key.client_id,
            client_secret=service_key.client_secret,
            resource_group=resource_group,
        )

        # Fetch deployment details
        deployment = client.deployment.get(
            deployment_id=deployment_id, resource_group=resource_group
        )

        deployment_url = deployment.deployment_url
        logger.info(
            f"Successfully resolved deployment ID {deployment_id} to URL: {deployment_url}"
        )

        return deployment_url

    except Exception as e:
        logger.error(f"Failed to fetch deployment URL for ID {deployment_id}: {e}")
        raise


def clear_deployment_cache() -> bool:
    """
    Clear all cached deployment data.

    This function delegates to cache_utils.clear_deployment_cache()
    to ensure a single source of truth for cache operations.

    Returns:
        bool: True if cache was cleared successfully, False otherwise
    """
    from utils.cache_utils import clear_deployment_cache as _clear_deployment_cache

    return _clear_deployment_cache()


def get_cache_stats() -> dict:
    """
    Get statistics about the deployment cache.

    Returns:
        dict: Dictionary containing cache statistics
    """
    from utils.cache_utils import get_cache_stats as _get_cache_stats

    return _get_cache_stats()


def fetch_all_deployments(
    service_key: ServiceKey,
    resource_group: str = "default",
    force_refresh: bool = False,
) -> list[dict]:
    """
    Fetch all deployments for a subaccount and extract their details.
    Results are cached to disk to avoid repeated API calls.

    Args:
        service_key: SAP AI Core service key credentials
        resource_group: Resource group for the deployment, defaults to "default"
        force_refresh: If True, bypass cache and fetch fresh data

    Returns:
        List of dictionaries containing:
        - id: Deployment ID
        - url: Deployment URL
        - model_name: Backend model name (if available)
        - created_at: Creation timestamp (if available)

    Raises:
        DeploymentFetchError: If fetching deployments fails (network, auth, timeout, etc.)
        CacheError: If cache operations fail
    """
    from utils.exceptions import DeploymentFetchError, CacheError
    from utils.error_ids import ErrorIDs
    import requests

    # Create cache key based on credentials and resource group
    key_str = f"{service_key.client_id}:{service_key.api_url}:{resource_group}"
    cache_key = hashlib.md5(key_str.encode()).hexdigest()

    try:
        with Cache(CACHE_DIR) as cache:
            # Check cache first (unless force_refresh is True)
            if not force_refresh:
                cached_data = cache.get(cache_key)
                if cached_data:
                    from utils.cache_utils import format_cache_expiry

                    expiry_seconds = int(cache.expire(cache_key) or 0)
                    formatted_expiry = format_cache_expiry(expiry_seconds)
                    logger.info(
                        f"Using cached deployments for resource group: {resource_group} (expires in {formatted_expiry})"
                    )
                    return cached_data

            logger.info(
                f"Fetching all deployments for resource group: {resource_group}"
            )

            try:
                client = AIAPIV2Client(
                    base_url=service_key.api_url + "/v2/lm",
                    auth_url=service_key.auth_url + "/oauth/token",
                    client_id=service_key.client_id,
                    client_secret=service_key.client_secret,
                    resource_group=resource_group,
                )

                # Query all deployments
                deployments = client.deployment.query()

                results = []
                for deployment in deployments.resources:
                    # Basic details
                    info = {
                        "id": deployment.id,
                        "url": deployment.deployment_url,
                        "created_at": str(deployment.created_at),
                        "model_name": None,
                    }

                    # Try to extract backend model name
                    try:
                        if hasattr(deployment, "details") and deployment.details:
                            details = deployment.details
                            if (
                                "resources" in details
                                and "backend_details" in details["resources"]
                            ):
                                backend_details = details["resources"][
                                    "backend_details"
                                ]
                                if (
                                    "model" in backend_details
                                    and "name" in backend_details["model"]
                                ):
                                    info["model_name"] = backend_details["model"][
                                        "name"
                                    ]
                    except Exception as e:
                        logger.debug(
                            f"Could not extract backend model for deployment {deployment.id}: {e}"
                        )

                    results.append(info)

                logger.info(
                    f"Found {len(results)} deployments. Caching for {CACHE_DURATION}s."
                )

                # Store in cache
                try:
                    cache.set(cache_key, results, expire=CACHE_DURATION)
                except Exception as e:
                    logger.warning(f"Failed to cache deployment results: {e}")
                    # Continue anyway - cache failure shouldn't fail the whole operation

                return results

            except requests.exceptions.Timeout as e:
                logger.error(
                    f"Timeout fetching deployments for {resource_group}: {e}",
                    extra={"error_id": ErrorIDs.DEPLOYMENT_FETCH_TIMEOUT},
                )
                raise DeploymentFetchError(f"Request timed out: {e}") from e

            except requests.exceptions.RequestException as e:
                logger.error(
                    f"Network error fetching deployments for {resource_group}: {e}",
                    extra={"error_id": ErrorIDs.DEPLOYMENT_FETCH_NETWORK},
                )
                raise DeploymentFetchError(f"Network error: {e}") from e

            except Exception as e:
                # Log any unexpected errors with generic error ID
                logger.error(
                    f"Unexpected error fetching deployments for {resource_group}: {e}",
                    extra={"error_id": ErrorIDs.DEPLOYMENT_FETCH_FAILED},
                )
                raise DeploymentFetchError(f"Failed to fetch deployments: {e}") from e

    except DeploymentFetchError:
        # Re-raise deployment errors as-is
        raise
    except Exception as e:
        logger.error(
            f"Cache error during deployment fetch: {e}",
            extra={"error_id": ErrorIDs.CACHE_OS_ERROR},
        )
        raise CacheError(f"Cache operation failed: {e}") from e
