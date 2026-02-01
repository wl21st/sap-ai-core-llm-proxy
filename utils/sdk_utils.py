import logging
from urllib.parse import urlparse

from ai_core_sdk.ai_core_v2_client import AICoreV2Client

from config import ServiceKey

logger = logging.getLogger(__name__)


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
