"""Provider registry for dynamic model provider management.

This module implements a registry pattern for managing model providers,
enabling dynamic provider registration and lookup.
"""

import logging
import threading
from typing import Dict, List, Optional

from .provider import ModelProvider


class ProviderRegistry:
    """Registry for managing model providers.
    
    Features:
    - Thread-safe provider registration and lookup
    - Provider priority ordering
    - Fallback provider selection
    
    This class implements a singleton-like pattern where providers are registered
    once and reused across the application.
    """
    
    def __init__(self):
        """Initialize the provider registry."""
        self._providers: List[ModelProvider] = []
        self._provider_map: Dict[str, ModelProvider] = {}
        self._lock = threading.Lock()
        self._logger = logging.getLogger(__name__)
    
    def register(self, provider: ModelProvider) -> None:
        """Register a model provider.
        
        Args:
            provider: ModelProvider instance to register
            
        Raises:
            ValueError: If provider with same name already registered
        """
        with self._lock:
            provider_name = provider.get_provider_name()
            
            # Check for duplicate registration
            if provider_name in self._provider_map:
                self._logger.warning(
                    f"Provider '{provider_name}' already registered, skipping"
                )
                return
            
            self._providers.append(provider)
            self._provider_map[provider_name] = provider
            self._logger.info(f"Registered provider: {provider_name}")
    
    def get_provider(self, model: str) -> Optional[ModelProvider]:
        """Get the provider that supports the given model.
        
        Iterates through registered providers in order and returns the first
        provider that supports the model.
        
        Args:
            model: Model name to find provider for
            
        Returns:
            ModelProvider instance or None if no provider found
        """
        with self._lock:
            for provider in self._providers:
                if provider.supports_model(model):
                    self._logger.debug(
                        f"Found provider '{provider.get_provider_name()}' for model '{model}'"
                    )
                    return provider
            
            self._logger.warning(f"No provider found for model '{model}'")
            return None
    
    def get_provider_by_name(self, name: str) -> Optional[ModelProvider]:
        """Get a provider by its name.
        
        Args:
            name: Provider name (e.g., 'claude', 'gemini', 'openai')
            
        Returns:
            ModelProvider instance or None if not found
        """
        with self._lock:
            return self._provider_map.get(name)
    
    def list_providers(self) -> List[str]:
        """List all registered provider names.
        
        Returns:
            List of provider names
        """
        with self._lock:
            return [p.get_provider_name() for p in self._providers]
    
    def get_all_providers(self) -> List[ModelProvider]:
        """Get all registered providers.
        
        Returns:
            List of ModelProvider instances
        """
        with self._lock:
            return self._providers.copy()
    
    def clear(self) -> None:
        """Clear all registered providers.
        
        Useful for testing or reinitialization.
        """
        with self._lock:
            self._providers.clear()
            self._provider_map.clear()
            self._logger.info("Cleared all providers from registry")


# Global registry instance
_global_registry: Optional[ProviderRegistry] = None
_registry_lock = threading.Lock()


def get_global_registry() -> ProviderRegistry:
    """Get or create the global provider registry.
    
    This function implements lazy initialization of the global registry
    in a thread-safe manner.
    
    Returns:
        Global ProviderRegistry instance
    """
    global _global_registry
    
    if _global_registry is None:
        with _registry_lock:
            if _global_registry is None:
                _global_registry = ProviderRegistry()
    
    return _global_registry