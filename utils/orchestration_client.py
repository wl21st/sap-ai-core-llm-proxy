"""
OrchestrationClient for SAP AI Core Orchestration V2.

Handles non-streaming and streaming inference requests via
POST {orchestration_url}/completion.

Responsibilities:
- Build OpenAI → Orchestration V2 request body mapping
- Inject Bearer token and AI-Resource-Group header
- Non-streaming invoke (returns OpenAI-compatible dict)
- Streaming invoke_stream (yields raw SSE chunks)
- HTTP 429 retry with exponential backoff
"""

import logging
from typing import Generator, Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from config.config_models import SubAccountConfig
from utils.retry import retry_on_rate_limit, RETRY_MAX_ATTEMPTS, RETRY_MIN_WAIT, RETRY_MAX_WAIT, RETRY_MULTIPLIER

logger = logging.getLogger(__name__)

# Retry decorator for orchestration requests (mirrors unified_retry but without botocore dep)
_orchestration_retry = retry(
    stop=stop_after_attempt(RETRY_MAX_ATTEMPTS),
    wait=wait_exponential(
        multiplier=RETRY_MULTIPLIER, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT
    ),
    retry=retry_on_rate_limit,
    before_sleep=lambda retry_state: logger.warning(
        "Orchestration rate limit hit, retrying in %s seconds (attempt %s/%s): %s",
        retry_state.next_action.sleep if retry_state.next_action else "unknown",
        retry_state.attempt_number,
        RETRY_MAX_ATTEMPTS,
        str(retry_state.outcome.exception()) if retry_state.outcome else "unknown error",
    ),
)


def build_request_body(
    model: str,
    messages: list[dict],
    params: dict,
    stream: bool = False,
) -> dict:
    """Map an OpenAI-format request to an Orchestration V2 request body.

    Args:
        model: The canonical model name (after alias resolution).
        messages: OpenAI messages array (list of {role, content} dicts).
        params: Additional OpenAI params (max_tokens, temperature, top_p, etc.).
        stream: Whether to request streaming SSE.

    Returns:
        Orchestration V2-compatible request body dict.
    """
    # Map supported OpenAI params → model_params
    model_params: dict = {}
    for key in (
        "max_tokens",
        "temperature",
        "top_p",
        "n",
        "stop",
        "presence_penalty",
        "frequency_penalty",
    ):
        if key in params and params[key] is not None:
            model_params[key] = params[key]

    body: dict = {
        "orchestration_config": {
            "module_configurations": {
                "llm_module_config": {
                    "model_name": model,
                    "model_params": model_params,
                },
                "templating_module_config": {
                    "template": messages,
                },
            }
        },
        "stream": stream,
    }
    return body


class OrchestrationClient:
    """HTTP client for SAP AI Core Orchestration V2 inference endpoint.

    Manages:
    - Request body construction (OpenAI → Orchestration V2 mapping)
    - Token injection from TokenManager
    - Non-streaming and streaming POST to {orchestration_url}/completion
    - HTTP 429 retry with exponential backoff

    Thread-safe: each call fetches a token independently via TokenManager.
    """

    def __init__(
        self,
        ca_cert_bundle: Optional[str] = None,
        timeout: int = 120,
    ) -> None:
        """Initialize the OrchestrationClient.

        Args:
            ca_cert_bundle: Optional CA certificate bundle path for TLS verification.
            timeout: Request timeout in seconds for non-streaming requests.
        """
        self._ca_cert_bundle = ca_cert_bundle
        self._timeout = timeout

    def _build_headers(self, subaccount: SubAccountConfig, token: str) -> dict:
        """Build request headers for an orchestration request.

        Args:
            subaccount: The selected subaccount config.
            token: A valid Bearer token for the subaccount.

        Returns:
            Headers dict.
        """
        headers = {
            "Authorization": f"Bearer {token}",
            "AI-Resource-Group": subaccount.resource_group,
            "Content-Type": "application/json",
        }
        if subaccount.service_key and subaccount.service_key.identity_zone_id:
            headers["AI-Tenant-Id"] = subaccount.service_key.identity_zone_id
        return headers

    def _get_completion_url(self, subaccount: SubAccountConfig) -> str:
        """Derive the /completion URL from the subaccount's orchestration_url.

        The stored URL may already end in /completion (explicit config) or may
        be the bare deployment base URL.

        Args:
            subaccount: The subaccount config.

        Returns:
            Full URL ending in /completion.

        Raises:
            ValueError: If the subaccount has no orchestration_url.
        """
        if not subaccount.orchestration_url:
            raise ValueError(
                f"Subaccount '{subaccount.name}' has no orchestration_url configured."
            )
        url = subaccount.orchestration_url.rstrip("/")
        if not url.endswith("/completion"):
            url = f"{url}/completion"
        return url

    def invoke(
        self,
        subaccount: SubAccountConfig,
        token: str,
        model: str,
        messages: list[dict],
        params: dict,
    ) -> dict:
        """Send a non-streaming inference request to Orchestration V2.

        Retries automatically on HTTP 429 (rate limit).

        Args:
            subaccount: The subaccount to route the request to.
            token: Valid Bearer token for the subaccount.
            model: Canonical model name.
            messages: OpenAI messages array.
            params: Additional request parameters (temperature, max_tokens, etc.).

        Returns:
            OpenAI-compatible response dict (forwarded as-is from Orchestration V2).

        Raises:
            requests.HTTPError: On non-retryable HTTP errors.
            RuntimeError: On unexpected errors.
        """
        body = build_request_body(model=model, messages=messages, params=params, stream=False)
        return self._invoke_with_retry(subaccount, token, body)

    @_orchestration_retry
    def _invoke_with_retry(
        self,
        subaccount: SubAccountConfig,
        token: str,
        body: dict,
    ) -> dict:
        """Internal: perform the HTTP POST with retry wrapping.

        Args:
            subaccount: Target subaccount.
            token: Bearer token.
            body: Orchestration V2 request body dict.

        Returns:
            OpenAI-compatible response dict.
        """
        url = self._get_completion_url(subaccount)
        headers = self._build_headers(subaccount, token)
        verify: str | bool = self._ca_cert_bundle if self._ca_cert_bundle else True

        logger.debug(
            "OrchestrationClient.invoke: POST %s model=%s",
            url,
            body.get("orchestration_config", {})
            .get("module_configurations", {})
            .get("llm_module_config", {})
            .get("model_name", "unknown"),
        )

        response = requests.post(
            url, json=body, headers=headers, timeout=self._timeout, verify=verify
        )
        if response.status_code == 429:
            # Raise so tenacity retry picks it up
            raise requests.HTTPError(
                f"429 Too Many Requests: {response.text}", response=response
            )
        response.raise_for_status()
        return response.json()

    def invoke_stream(
        self,
        subaccount: SubAccountConfig,
        token: str,
        model: str,
        messages: list[dict],
        params: dict,
    ) -> Generator[bytes, None, None]:
        """Send a streaming inference request to Orchestration V2.

        Yields raw SSE bytes chunks as received from the server.
        Orchestration V2 returns OpenAI-compatible SSE, so chunks are forwarded
        as-is.

        Retries are NOT applied to streaming requests (the stream is live).

        Args:
            subaccount: The subaccount to route the request to.
            token: Valid Bearer token for the subaccount.
            model: Canonical model name.
            messages: OpenAI messages array.
            params: Additional request parameters.

        Yields:
            Raw SSE byte chunks.

        Raises:
            requests.HTTPError: On HTTP errors (including 429).
            RuntimeError: On unexpected errors.
        """
        body = build_request_body(model=model, messages=messages, params=params, stream=True)
        url = self._get_completion_url(subaccount)
        headers = self._build_headers(subaccount, token)
        verify: str | bool = self._ca_cert_bundle if self._ca_cert_bundle else True

        logger.debug(
            "OrchestrationClient.invoke_stream: POST %s model=%s",
            url,
            model,
        )

        with requests.post(
            url,
            json=body,
            headers=headers,
            timeout=self._timeout,
            verify=verify,
            stream=True,
        ) as response:
            if response.status_code == 429:
                raise requests.HTTPError(
                    f"429 Too Many Requests: {response.text}", response=response
                )
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=None):
                if chunk:
                    yield chunk


# Global singleton
_client: Optional[OrchestrationClient] = None


def get_orchestration_client(
    ca_cert_bundle: Optional[str] = None,
) -> OrchestrationClient:
    """Get or create the global OrchestrationClient singleton.

    Args:
        ca_cert_bundle: Optional CA cert bundle for TLS verification.
            Only used on first creation; ignored on subsequent calls.

    Returns:
        The global OrchestrationClient instance.
    """
    global _client
    if _client is None:
        _client = OrchestrationClient(ca_cert_bundle=ca_cert_bundle)
    return _client
