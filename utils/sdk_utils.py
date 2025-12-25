from typing import Optional
from urllib.parse import urlparse


def extract_deployment_id(deployment_url: str) -> Optional[str]:
    """
    Extract deployment ID from SAP AI Core deployment URL.

    Args:
        deployment_url: Full deployment URL (e.g., "https://api.ai.prod.eu-central-1.aws.ml.hana.ondemand.com/v2/inference/deployments/{deployment_id}")

    Returns:
        Deployment ID string if found, None otherwise

    Raises:
        ValueError: If URL format is invalid
    """
    if not deployment_url or not isinstance(deployment_url, str):
        raise ValueError("URL must be a non-empty string")

    try:
        parsed = urlparse(deployment_url)
        path = parsed.path.rstrip('/')  # Remove trailing slash if present

        # Expected pattern: /v2/inference/deployments/{deployment_id}
        if '/deployments/' in path:
            deployment_id = path.split('/deployments/')[-1].split('/')[0]
            return deployment_id.strip() if deployment_id else None

        return None
    except Exception as e:
        raise ValueError(f"Failed to parse URL: {e}")
