"""Model detection and provider identification.

This module provides model type detection and provider identification functionality,
extracting the logic from proxy_server.py for better modularity.
"""

import logging
import re
from typing import Optional

from .registry import ProviderRegistry, get_global_registry


class ModelDetector:
    """Detects model types and identifies appropriate providers.
    
    Features:
    - Provider-based detection using registry
    - Backward-compatible detection functions
    - Version detection for Claude models
    """
    
    def __init__(self, registry: Optional[ProviderRegistry] = None):
        """Initialize detector with provider registry.
        
        Args:
            registry: ProviderRegistry instance (uses global if None)
        """
        self.registry = registry or get_global_registry()
        self._logger = logging.getLogger(__name__)
    
    def detect_provider(self, model: str) -> Optional[str]:
        """Detect which provider supports the given model.
        
        Args:
            model: Model name to detect
            
        Returns:
            Provider name or None if no provider found
        """
        provider = self.registry.get_provider(model)
        return provider.get_provider_name() if provider else None
    
    def is_claude_model(self, model: str) -> bool:
        """Check if model is a Claude model.
        
        Supports detection of:
        - claude-3.5-sonnet
        - claude-3.7-sonnet
        - claude-4-sonnet, claude-4-opus
        - claude-4.5-sonnet
        - anthropic-- prefixed variants
        - Partial names (clau, claud, sonnet, etc.)
        
        Args:
            model: Model name to check
            
        Returns:
            True if Claude model, False otherwise
        """
        keywords = ["claude", "clau", "claud", "sonnet", "sonne", "sonn"]
        return any(keyword in model.lower() for keyword in keywords)
    
    def is_gemini_model(self, model: str) -> bool:
        """Check if model is a Gemini model.
        
        Supports detection of:
        - gemini-1.5-pro, gemini-1.5-flash
        - gemini-2.5-pro, gemini-2.5-flash
        - gemini-pro, gemini-flash
        
        Args:
            model: Model name to check
            
        Returns:
            True if Gemini model, False otherwise
        """
        keywords = ["gemini", "gemini-1.5", "gemini-2.5", "gemini-pro", "gemini-flash"]
        return any(keyword in model.lower() for keyword in keywords)
    
    def is_claude_37_or_4(self, model: str) -> bool:
        """Check if model is Claude 3.7, 4, or 4.5.
        
        These versions use different endpoints (/converse vs /invoke).
        
        Args:
            model: Model name to check
            
        Returns:
            True if Claude 3.7/4/4.5, False otherwise
        """
        # Check for explicit version numbers
        if any(version in model for version in ["3.7", "4", "4.5"]):
            return True
        
        # If it's a Claude model but doesn't contain "3.5", assume newer version
        if self.is_claude_model(model) and "3.5" not in model:
            return True
        
        return False
    
    def get_model_version(self, model: str) -> Optional[str]:
        """Extract version number from model name.
        
        Args:
            model: Model name
            
        Returns:
            Version string (e.g., "3.5", "4", "4.5") or None
        """
        # Try to extract version pattern like "3.5", "4", "4.5"
        version_match = re.search(r'(\d+(?:\.\d+)?)', model)
        if version_match:
            return version_match.group(1)
        
        return None


# Module-level instance for backward compatibility
_default_detector: Optional[ModelDetector] = None


def get_default_detector() -> ModelDetector:
    """Get or create default detector instance.
    
    Returns:
        Default ModelDetector instance
    """
    global _default_detector
    if _default_detector is None:
        _default_detector = ModelDetector()
    return _default_detector


# Backward compatibility: Module-level functions
def is_claude_model(model: str) -> bool:
    """Backward compatible function for Claude detection.
    
    Args:
        model: Model name to check
        
    Returns:
        True if Claude model, False otherwise
    """
    return get_default_detector().is_claude_model(model)


def is_gemini_model(model: str) -> bool:
    """Backward compatible function for Gemini detection.
    
    Args:
        model: Model name to check
        
    Returns:
        True if Gemini model, False otherwise
    """
    return get_default_detector().is_gemini_model(model)


def is_claude_37_or_4(model: str) -> bool:
    """Backward compatible function for Claude 3.7/4 detection.
    
    Args:
        model: Model name to check
        
    Returns:
        True if Claude 3.7/4/4.5, False otherwise
    """
    return get_default_detector().is_claude_37_or_4(model)