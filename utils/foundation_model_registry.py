"""
Foundation Model Registry for SAP Orchestration V2.

Discovers and caches available foundation models from SAP AI Core's
GET /v2/lm/foundation-models endpoint. Falls back to a static model list
when the API is unavailable.
"""

import logging
import threading
import time
from typing import Optional

import requests

from config.config_models import SubAccountConfig

logger = logging.getLogger(__name__)

# Cache TTL: 24 hours in seconds
_CACHE_TTL_SECONDS = 24 * 60 * 60

# Static fallback model list (from SAP AI Core Orchestration V2 investigation doc, SDK v6.7.0)
STATIC_FALLBACK_MODELS: list[dict] = [
    # OpenAI models
    {"name": "gpt-4o", "provider": "openai"},
    {"name": "gpt-4o-mini", "provider": "openai"},
    {"name": "gpt-4.1", "provider": "openai"},
    {"name": "gpt-4.1-mini", "provider": "openai"},
    {"name": "gpt-4.1-nano", "provider": "openai"},
    {"name": "gpt-5", "provider": "openai"},
    {"name": "gpt-5-mini", "provider": "openai"},
    {"name": "gpt-5-nano", "provider": "openai"},
    {"name": "o1", "provider": "openai"},
    {"name": "o3", "provider": "openai"},
    {"name": "o3-mini", "provider": "openai"},
    {"name": "o4-mini", "provider": "openai"},
    # Anthropic models
    {"name": "anthropic--claude-3-haiku", "provider": "anthropic"},
    {"name": "anthropic--claude-3.5-sonnet", "provider": "anthropic"},
    {"name": "anthropic--claude-3.7-sonnet", "provider": "anthropic"},
    {"name": "anthropic--claude-4-sonnet", "provider": "anthropic"},
    {"name": "anthropic--claude-4-opus", "provider": "anthropic"},
    {"name": "anthropic--claude-4.5-sonnet", "provider": "anthropic"},
    {"name": "anthropic--claude-4.5-haiku", "provider": "anthropic"},
    # Google Gemini models
    {"name": "gemini-2.0-flash", "provider": "google"},
    {"name": "gemini-2.0-flash-lite", "provider": "google"},
    {"name": "gemini-2.5-flash", "provider": "google"},
    {"name": "gemini-2.5-pro", "provider": "google"},
    {"name": "gemini-2.5-flash-lite", "provider": "google"},
    # MistralAI models
    {"name": "mistralai--mistral-small-instruct", "provider": "mistralai"},
    {"name": "mistralai--mistral-medium-instruct", "provider": "mistralai"},
    {"name": "mistralai--mistral-large-instruct", "provider": "mistralai"},
    # Amazon models
    {"name": "amazon--nova-lite", "provider": "amazon"},
    {"name": "amazon--nova-micro", "provider": "amazon"},
    {"name": "amazon--nova-pro", "provider": "amazon"},
    {"name": "amazon--amazon--nova-premier", "provider": "amazon"},
    # Cohere models
    {"name": "cohere--command-a-reasoning", "provider": "cohere"},
    {"name": "cohere--reranker", "provider": "cohere"},
    # Perplexity models
    {"name": "sonar", "provider": "perplexity"},
    {"name": "sonar-pro", "provider": "perplexity"},
]


class FoundationModelRegistry:
    """Registry of available foundation models from SAP AI Core Orchestration V2.

    Fetches models from GET /v2/lm/foundation-models per subaccount and caches
    them in memory for 24 hours. Falls back to a static model list when the API
    is unavailable.

    Thread-safe: all shared state is protected by a threading.Lock.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Map of model_name -> model_info dict (union across all subaccounts)
        self._models: dict[str, dict] = {}
        # Per-subaccount cache entries: {subaccount_name: (models, fetched_at)}
        self._cache: dict[str, tuple[list[dict], float]] = {}
        # Whether we've ever populated the registry
        self._initialized = False

    def populate(
        self,
        subaccounts: dict[str, SubAccountConfig],
        token_managers: dict,
        ca_cert_bundle: Optional[str] = None,
    ) -> None:
        """Populate the registry from all configured subaccounts at startup.

        Args:
            subaccounts: Dict of subaccount name -> SubAccountConfig
            token_managers: Dict of subaccount name -> TokenManager
            ca_cert_bundle: Optional CA certificate bundle for TLS verification
        """
        with self._lock:
            self._models.clear()
            any_success = False

            for sub_name, sub_config in subaccounts.items():
                if not sub_config.orchestration_url:
                    continue  # Skip legacy subaccounts
                token_manager = token_managers.get(sub_name)
                if not token_manager:
                    continue

                models = self._fetch_models_locked(
                    sub_config, token_manager, ca_cert_bundle
                )
                if models:
                    self._cache[sub_name] = (models, time.monotonic())
                    for m in models:
                        name = m.get("name") or m.get("model_name") or m.get("id", "")
                        if name and name not in self._models:
                            self._models[name] = m
                    any_success = True
                    logger.info(
                        "Foundation model registry: loaded %d models from subaccount '%s'",
                        len(models),
                        sub_name,
                    )

            if not any_success:
                logger.warning(
                    "Foundation model registry: could not fetch models from any subaccount. "
                    "Using static fallback model list (%d models).",
                    len(STATIC_FALLBACK_MODELS),
                )
                self._use_static_fallback()

            self._initialized = True
            logger.info(
                "Foundation model registry initialized with %d total models.",
                len(self._models),
            )

    def _fetch_models_locked(
        self,
        sub_config: SubAccountConfig,
        token_manager: object,
        ca_cert_bundle: Optional[str],
    ) -> list[dict]:
        """Fetch foundation models from GET /v2/lm/foundation-models.

        Must be called with self._lock held.

        Args:
            sub_config: Subaccount configuration
            token_manager: TokenManager for this subaccount
            ca_cert_bundle: Optional CA cert bundle path

        Returns:
            List of model info dicts, or [] on failure
        """
        if not sub_config.service_key or not sub_config.service_key.api_url:
            logger.warning(
                "Cannot fetch foundation models for '%s': service key not initialized",
                sub_config.name,
            )
            return []

        try:
            token: str = token_manager.get_token()  # type: ignore[union-attr]
            api_url = sub_config.service_key.api_url.rstrip("/")
            url = f"{api_url}/v2/lm/foundation-models"
            headers = {
                "Authorization": f"Bearer {token}",
                "AI-Resource-Group": sub_config.resource_group,
                "Content-Type": "application/json",
            }
            verify: str | bool = ca_cert_bundle if ca_cert_bundle else True
            response = requests.get(url, headers=headers, timeout=15, verify=verify)
            response.raise_for_status()
            data = response.json()
            # Expected structure: {"resources": [...], "count": N}
            resources = data.get("resources", data.get("models", []))
            if not isinstance(resources, list):
                resources = []
            logger.debug(
                "Fetched %d foundation models from '%s'",
                len(resources),
                sub_config.name,
            )
            return resources
        except Exception as e:
            logger.warning(
                "Failed to fetch foundation models from '%s': %s",
                sub_config.name,
                e,
            )
            return []

    def _use_static_fallback(self) -> None:
        """Populate registry from STATIC_FALLBACK_MODELS.

        Must be called with self._lock held.
        """
        for m in STATIC_FALLBACK_MODELS:
            name = m.get("name", "")
            if name:
                self._models[name] = m

    def get_all_models(self) -> list[dict]:
        """Get all known foundation models.

        Returns:
            List of model info dicts with at least a 'name' key.
        """
        with self._lock:
            if not self._initialized:
                # Return static fallback until populated
                return list(STATIC_FALLBACK_MODELS)
            return list(self._models.values())

    def get_model_names(self) -> list[str]:
        """Get list of all known model names.

        Returns:
            Sorted list of canonical model name strings.
        """
        with self._lock:
            if not self._initialized:
                return sorted(m["name"] for m in STATIC_FALLBACK_MODELS)
            return sorted(self._models.keys())

    def is_known_model(self, model_name: str) -> bool:
        """Check if a model name is known in the registry.

        Args:
            model_name: The model name to look up

        Returns:
            True if the model is known, False otherwise.
        """
        with self._lock:
            if not self._initialized:
                return any(m["name"] == model_name for m in STATIC_FALLBACK_MODELS)
            return model_name in self._models

    def refresh(
        self,
        subaccounts: dict[str, SubAccountConfig],
        token_managers: dict,
        ca_cert_bundle: Optional[str] = None,
    ) -> None:
        """Refresh the registry, respecting the cache TTL.

        Only refetches subaccounts whose cache has expired.

        Args:
            subaccounts: Dict of subaccount name -> SubAccountConfig
            token_managers: Dict of subaccount name -> TokenManager
            ca_cert_bundle: Optional CA cert bundle path
        """
        now = time.monotonic()
        with self._lock:
            for sub_name, sub_config in subaccounts.items():
                if not sub_config.orchestration_url:
                    continue
                cached = self._cache.get(sub_name)
                if cached:
                    _, fetched_at = cached
                    if now - fetched_at < _CACHE_TTL_SECONDS:
                        continue  # Cache still valid

                token_manager = token_managers.get(sub_name)
                if not token_manager:
                    continue
                models = self._fetch_models_locked(
                    sub_config, token_manager, ca_cert_bundle
                )
                if models:
                    self._cache[sub_name] = (models, now)
                    # Merge fresh models into registry
                    for m in models:
                        name = m.get("name") or m.get("model_name") or m.get("id", "")
                        if name:
                            self._models[name] = m


# Global singleton registry
_registry: Optional[FoundationModelRegistry] = None
_registry_lock = threading.Lock()


def get_registry() -> FoundationModelRegistry:
    """Get or create the global FoundationModelRegistry singleton.

    Returns:
        The global FoundationModelRegistry instance.
    """
    global _registry
    if _registry is not None:
        return _registry
    with _registry_lock:
        if _registry is None:
            _registry = FoundationModelRegistry()
    return _registry
