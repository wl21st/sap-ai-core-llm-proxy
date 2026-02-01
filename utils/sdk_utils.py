import logging
from urllib.parse import urlparse
import os
import hashlib
from diskcache import Cache

from ai_core_sdk.ai_core_v2_client import AICoreV2Client

# Avoid circular import by not importing config.config_models here if it imports config_parser
# Wait, config_models should be safe. Let's check config/__init__.py
# config/__init__.py imports config_parser which imports sdk_utils.
# We must avoid importing from 'config' package directly if it triggers __init__.py

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
        ValueError: If URL format is invalid
    """
    if not deployment_url or not isinstance(deployment_url, str):
        raise ValueError("URL must be a non-empty string")

    try:
        parsed = urlparse(deployment_url)
        path = parsed.path.rstrip("/")  # Remove trailing slash if present

        # Expected pattern: /v2/inference/deployments/{deployment_id}
        if "/deployments/" in path:
            deployment_id = path.split("/deployments/")[-1].split("/")[0]

            if deployment_id:
                return deployment_id.strip()

        raise ValueError(f"No deployment_id in URL: {deployment_url}")
    except Exception as e:
        raise ValueError(f"Failed to parse URL: {e}")


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
            base_url=service_key.api_url,
            auth_url=service_key.auth_url,
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


def fetch_all_deployments(
    service_key: ServiceKey, resource_group: str = "default"
) -> list[dict]:
    """
    Fetch all deployments for a subaccount and extract their details.
    Results are cached to disk to avoid repeated API calls.

    Args:
        service_key: SAP AI Core service key credentials
        resource_group: Resource group for the deployment, defaults to "default"

    Returns:
        List of dictionaries containing:
        - id: Deployment ID
        - url: Deployment URL
        - model_name: Backend model name (if available)
        - created_at: Creation timestamp (if available)
    """
    # Create cache key based on credentials and resource group
    key_str = f"{service_key.client_id}:{service_key.api_url}:{resource_group}"
    cache_key = hashlib.md5(key_str.encode()).hexdigest()

    with Cache(CACHE_DIR) as cache:
        # Check cache first
        cached_data = cache.get(cache_key)
        if cached_data:
            logger.info(
                f"Using cached deployments for resource group: {resource_group} (expires in {int(cache.expire(cache_key) or 0)}s)"
            )
            return cached_data

        logger.info(f"Fetching all deployments for resource group: {resource_group}")

        try:
            client = AICoreV2Client(
                base_url=service_key.api_url,
                auth_url=service_key.auth_url,
                client_id=service_key.client_id,
                client_secret=service_key.client_secret,
                resource_group=resource_group,
            )

            # Query all deployments
            # Note: The SDK might handle pagination internally or return a list
            deployments = client.deployment.query(resource_group=resource_group)

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
                # Structure expected: deployment.details["resources"]["backend_details"]["model"]["name"]
                try:
                    if hasattr(deployment, "details") and deployment.details:
                        details = deployment.details
                        if (
                            "resources" in details
                            and "backend_details" in details["resources"]
                        ):
                            backend_details = details["resources"]["backend_details"]
                            if (
                                "model" in backend_details
                                and "name" in backend_details["model"]
                            ):
                                info["model_name"] = backend_details["model"]["name"]
                except Exception as e:
                    logger.debug(
                        f"Could not extract backend model for deployment {deployment.id}: {e}"
                    )

                results.append(info)

            logger.info(
                f"Found {len(results)} deployments. Caching for {CACHE_DURATION}s."
            )

            # Store in cache
            cache.set(cache_key, results, expire=CACHE_DURATION)

            return results

        except Exception as e:
            logger.error(f"Failed to fetch deployments: {e}")
            return []
