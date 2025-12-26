from urllib.parse import urlparse


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
