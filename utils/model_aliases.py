"""
Model name alias resolution for SAP AI Core Orchestration V2.

Maps common/short model names (sent by clients) to canonical Orchestration V2
model names (as returned by GET /v2/lm/foundation-models).

Default aliases cover the most common shorthand patterns.
Additional aliases can be loaded from config/aliases.json at runtime.
"""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Default alias map: common/shorthand name → canonical Orchestration V2 name
#
# Rules:
# - Keys are lowercased variants clients are likely to send
# - Values are canonical names as listed in the foundation model registry
# - Longer / more-specific keys should come before shorter ones to ensure
#   the most-specific match wins (dict lookup is O(1) so order doesn't
#   actually matter, but listing order aids readability)
DEFAULT_ALIASES: dict[str, str] = {
    # --- Anthropic Claude ---
    # claude-3-haiku variants
    "claude-3-haiku": "anthropic--claude-3-haiku",
    "claude-3-haiku-20240307": "anthropic--claude-3-haiku",
    # claude-3.5-sonnet variants
    "claude-3-5-sonnet": "anthropic--claude-3.5-sonnet",
    "claude-3.5-sonnet": "anthropic--claude-3.5-sonnet",
    "claude-3-5-sonnet-20241022": "anthropic--claude-3.5-sonnet",
    "claude-3.5-sonnet-20241022": "anthropic--claude-3.5-sonnet",
    # claude-3.7-sonnet variants
    "claude-3-7-sonnet": "anthropic--claude-3.7-sonnet",
    "claude-3.7-sonnet": "anthropic--claude-3.7-sonnet",
    "claude-3-7-sonnet-20250219": "anthropic--claude-3.7-sonnet",
    "claude-3.7-sonnet-20250219": "anthropic--claude-3.7-sonnet",
    # claude-4-sonnet variants
    "claude-4-sonnet": "anthropic--claude-4-sonnet",
    "claude-sonnet-4": "anthropic--claude-4-sonnet",
    "claude-sonnet-4-5": "anthropic--claude-4.5-sonnet",
    # claude-4.5-sonnet variants
    "claude-4.5-sonnet": "anthropic--claude-4.5-sonnet",
    "claude-4-5-sonnet": "anthropic--claude-4.5-sonnet",
    # claude-4-opus
    "claude-4-opus": "anthropic--claude-4-opus",
    "claude-opus-4": "anthropic--claude-4-opus",
    # claude-4.5-haiku
    "claude-4.5-haiku": "anthropic--claude-4.5-haiku",
    "claude-4-5-haiku": "anthropic--claude-4.5-haiku",
    "haiku-4.5": "anthropic--claude-4.5-haiku",
    # Bare shorthand (resolve to latest sonnet as reasonable default)
    "claude": "anthropic--claude-4.5-sonnet",
    "claude-sonnet": "anthropic--claude-4.5-sonnet",
    "claude-haiku": "anthropic--claude-4.5-haiku",
    "claude-opus": "anthropic--claude-4-opus",
    # sap-ai-core style: anthropic-- prefix but without sub-version
    "anthropic--claude-3-sonnet": "anthropic--claude-3.5-sonnet",
    "anthropic--claude-3-haiku": "anthropic--claude-3-haiku",  # already canonical
    # --- Google Gemini ---
    "gemini-2-flash": "gemini-2.0-flash",
    "gemini-2.0-flash-001": "gemini-2.0-flash",
    "gemini-flash": "gemini-2.5-flash",
    "gemini-flash-lite": "gemini-2.5-flash-lite",
    "gemini-pro": "gemini-2.5-pro",
    "gemini-2-pro": "gemini-2.5-pro",
    "gemini-2.5-pro-001": "gemini-2.5-pro",
    # --- OpenAI ---
    # gpt-4 family → gpt-4o as reasonable canonical
    "gpt-4": "gpt-4o",
    "gpt-4-turbo": "gpt-4o",
    "gpt-4-turbo-preview": "gpt-4o",
    "gpt-4o-2024-05-13": "gpt-4o",
    "gpt-4o-2024-08-06": "gpt-4o",
    # gpt-4o-mini
    "gpt-4o-mini-2024-07-18": "gpt-4o-mini",
    # gpt-4.1 family
    "gpt-4.1-2025-04-14": "gpt-4.1",
    # --- Amazon Nova ---
    "nova-lite": "amazon--nova-lite",
    "nova-micro": "amazon--nova-micro",
    "nova-pro": "amazon--nova-pro",
    "nova-premier": "amazon--amazon--nova-premier",
    # --- Mistral ---
    "mistral-small": "mistralai--mistral-small-instruct",
    "mistral-medium": "mistralai--mistral-medium-instruct",
    "mistral-large": "mistralai--mistral-large-instruct",
    "mistral-large-instruct": "mistralai--mistral-large-instruct",
    # --- Cohere ---
    "command-a": "cohere--command-a-reasoning",
    "command-a-reasoning": "cohere--command-a-reasoning",
    # --- Perplexity ---
    "sonar-pro": "sonar-pro",  # already canonical
}


def resolve_model_name(
    name: str,
    aliases: Optional[dict[str, str]] = None,
) -> str:
    """Resolve a model name to its canonical Orchestration V2 equivalent.

    Lookup order:
    1. Exact match in aliases (case-sensitive, then case-insensitive)
    2. Pass through unchanged if no alias found

    Args:
        name: The model name requested by the client.
        aliases: Alias map to use. Defaults to DEFAULT_ALIASES if None.

    Returns:
        The canonical model name (or the original name if no alias found).
    """
    effective_aliases = aliases if aliases is not None else DEFAULT_ALIASES

    # 1. Exact case-sensitive match
    if name in effective_aliases:
        resolved = effective_aliases[name]
        if resolved != name:
            logger.debug("Model alias resolved: '%s' → '%s'", name, resolved)
        return resolved

    # 2. Case-insensitive fallback
    name_lower = name.lower()
    for alias_key, canonical in effective_aliases.items():
        if alias_key.lower() == name_lower:
            logger.debug(
                "Model alias resolved (case-insensitive): '%s' → '%s'", name, canonical
            )
            return canonical

    # 3. No alias found — pass through unchanged
    return name


def load_aliases_from_file(
    aliases_path: str,
    base_aliases: Optional[dict[str, str]] = None,
) -> dict[str, str]:
    """Load model aliases from a JSON file and merge with base aliases.

    The file should contain a flat JSON object mapping alias → canonical name:
    ```json
    {
      "my-custom-model": "anthropic--claude-4.5-sonnet",
      "internal-gpt": "gpt-4o"
    }
    ```

    File aliases take precedence over base_aliases for the same key.

    Args:
        aliases_path: Path to the aliases JSON file.
        base_aliases: Base alias map to extend. Defaults to DEFAULT_ALIASES.

    Returns:
        Merged alias dict (base + file overrides).
    """
    result = dict(base_aliases if base_aliases is not None else DEFAULT_ALIASES)

    if not os.path.exists(aliases_path):
        logger.warning(
            "Aliases file not found: '%s'. Using default aliases only.", aliases_path
        )
        return result

    try:
        with open(aliases_path, "r") as f:
            file_aliases = json.load(f)
        if not isinstance(file_aliases, dict):
            logger.warning(
                "Aliases file '%s' must contain a JSON object. Ignoring.", aliases_path
            )
            return result
        result.update(file_aliases)
        logger.info(
            "Loaded %d additional model aliases from '%s'", len(file_aliases), aliases_path
        )
    except json.JSONDecodeError as e:
        logger.warning(
            "Could not parse aliases file '%s': %s. Using default aliases.", aliases_path, e
        )
    except OSError as e:
        logger.warning(
            "Could not read aliases file '%s': %s. Using default aliases.", aliases_path, e
        )

    return result
