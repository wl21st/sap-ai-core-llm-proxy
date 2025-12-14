"""Unit tests for models.registry module.

Tests the ProviderRegistry class and global registry functions.
"""

import pytest
import threading
import time
from models.registry import ProviderRegistry, get_global_registry
from models.claude_provider import ClaudeProvider
from models.gemini_provider import GeminiProvider
from models.openai_provider import OpenAIProvider


class TestProviderRegistry:
    """Test cases for ProviderRegistry class."""
    
    @pytest.fixture
    def registry(self):
        """Create a fresh ProviderRegistry instance."""
        return ProviderRegistry()
    
    # Registration Tests
    def test_register_single_provider(self, registry):
        """Test registering a single provider."""
        provider = ClaudeProvider()
        registry.register(provider)
        
        assert len(registry.list_providers()) == 1
        assert "claude" in registry.list_providers()
    
    def test_register_multiple_providers(self, registry):
        """Test registering multiple providers."""
        registry.register(ClaudeProvider())
        registry.register(GeminiProvider())
        registry.register(OpenAIProvider())
        
        assert len(registry.list_providers()) == 3
        assert set(registry.list_providers()) == {"claude", "gemini", "openai"}
    
    def test_register_duplicate_provider_skipped(self, registry):
        """Test registering duplicate provider is skipped."""
        registry.register(ClaudeProvider())
        registry.register(ClaudeProvider())  # Duplicate
        
        assert len(registry.list_providers()) == 1
    
    # Provider Lookup Tests
    def test_get_provider_claude(self, registry):
        """Test getting Claude provider by model name."""
        registry.register(ClaudeProvider())
        registry.register(GeminiProvider())
        registry.register(OpenAIProvider())
        
        provider = registry.get_provider("claude-4.5-sonnet")
        assert provider is not None
        assert provider.get_provider_name() == "claude"
    
    def test_get_provider_gemini(self, registry):
        """Test getting Gemini provider by model name."""
        registry.register(ClaudeProvider())
        registry.register(GeminiProvider())
        registry.register(OpenAIProvider())
        
        provider = registry.get_provider("gemini-2.5-pro")
        assert provider is not None
        assert provider.get_provider_name() == "gemini"
    
    def test_get_provider_openai(self, registry):
        """Test getting OpenAI provider by model name."""
        registry.register(ClaudeProvider())
        registry.register(GeminiProvider())
        registry.register(OpenAIProvider())
        
        provider = registry.get_provider("gpt-4o")
        assert provider is not None
        assert provider.get_provider_name() == "openai"
    
    def test_get_provider_fallback_to_openai(self, registry):
        """Test unknown models fallback to OpenAI provider."""
        registry.register(ClaudeProvider())
        registry.register(GeminiProvider())
        registry.register(OpenAIProvider())
        
        provider = registry.get_provider("unknown-model")
        assert provider is not None
        assert provider.get_provider_name() == "openai"
    
    def test_get_provider_not_found(self, registry):
        """Test get_provider returns None when no provider registered."""
        provider = registry.get_provider("any-model")
        assert provider is None
    
    def test_get_provider_priority_order(self, registry):
        """Test providers are checked in registration order."""
        # Register Claude first, then OpenAI
        registry.register(ClaudeProvider())
        registry.register(OpenAIProvider())
        
        # Claude model should match Claude provider (first match wins)
        provider = registry.get_provider("claude-4.5-sonnet")
        assert provider.get_provider_name() == "claude"
        
        # Unknown model should match OpenAI (fallback)
        provider2 = registry.get_provider("unknown-model")
        assert provider2.get_provider_name() == "openai"
    
    # Provider Lookup by Name Tests
    def test_get_provider_by_name_found(self, registry):
        """Test getting provider by name."""
        registry.register(ClaudeProvider())
        
        provider = registry.get_provider_by_name("claude")
        assert provider is not None
        assert provider.get_provider_name() == "claude"
    
    def test_get_provider_by_name_not_found(self, registry):
        """Test getting provider by name returns None if not found."""
        provider = registry.get_provider_by_name("nonexistent")
        assert provider is None
    
    # List Providers Tests
    def test_list_providers_empty(self, registry):
        """Test list_providers returns empty list initially."""
        assert registry.list_providers() == []
    
    def test_list_providers_multiple(self, registry):
        """Test list_providers returns all provider names."""
        registry.register(ClaudeProvider())
        registry.register(GeminiProvider())
        
        providers = registry.list_providers()
        assert len(providers) == 2
        assert "claude" in providers
        assert "gemini" in providers
    
    # Get All Providers Tests
    def test_get_all_providers_empty(self, registry):
        """Test get_all_providers returns empty list initially."""
        assert registry.get_all_providers() == []
    
    def test_get_all_providers_returns_copy(self, registry):
        """Test get_all_providers returns a copy, not original list."""
        registry.register(ClaudeProvider())
        
        providers1 = registry.get_all_providers()
        providers2 = registry.get_all_providers()
        
        assert providers1 is not providers2  # Different list objects
        assert len(providers1) == len(providers2)
    
    # Clear Tests
    def test_clear_removes_all_providers(self, registry):
        """Test clear removes all providers."""
        registry.register(ClaudeProvider())
        registry.register(GeminiProvider())
        
        assert len(registry.list_providers()) == 2
        
        registry.clear()
        
        assert len(registry.list_providers()) == 0
        assert registry.get_provider("claude-4.5-sonnet") is None


class TestGlobalRegistry:
    """Test cases for global registry functions."""
    
    def test_get_global_registry_returns_instance(self):
        """Test get_global_registry returns a registry instance."""
        registry = get_global_registry()
        assert isinstance(registry, ProviderRegistry)
    
    def test_get_global_registry_returns_same_instance(self):
        """Test get_global_registry returns same instance (singleton)."""
        registry1 = get_global_registry()
        registry2 = get_global_registry()
        assert registry1 is registry2
    
    def test_global_registry_persists_registrations(self):
        """Test global registry persists registrations across calls."""
        registry = get_global_registry()
        initial_count = len(registry.list_providers())
        
        # Register a provider
        registry.register(ClaudeProvider())
        
        # Get registry again
        registry2 = get_global_registry()
        assert len(registry2.list_providers()) == initial_count + 1


class TestThreadSafety:
    """Test thread safety of ProviderRegistry."""
    
    def test_concurrent_registration(self):
        """Test concurrent provider registration is thread-safe."""
        registry = ProviderRegistry()
        results = []
        
        def register_provider(provider_class):
            try:
                registry.register(provider_class())
                results.append(True)
            except Exception as e:
                results.append(False)
        
        # Create threads to register providers concurrently
        threads = [
            threading.Thread(target=register_provider, args=(ClaudeProvider,)),
            threading.Thread(target=register_provider, args=(GeminiProvider,)),
            threading.Thread(target=register_provider, args=(OpenAIProvider,)),
        ]
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All registrations should succeed
        assert all(results)
        assert len(registry.list_providers()) == 3
    
    def test_concurrent_lookup(self):
        """Test concurrent provider lookup is thread-safe."""
        registry = ProviderRegistry()
        registry.register(ClaudeProvider())
        registry.register(GeminiProvider())
        registry.register(OpenAIProvider())
        
        results = []
        
        def lookup_provider(model):
            try:
                provider = registry.get_provider(model)
                results.append(provider is not None)
            except Exception:
                results.append(False)
        
        # Create threads to lookup providers concurrently
        models = ["claude-4.5-sonnet", "gemini-2.5-pro", "gpt-4o"] * 10
        threads = [
            threading.Thread(target=lookup_provider, args=(model,))
            for model in models
        ]
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All lookups should succeed
        assert all(results)
        assert len(results) == 30