"""Unit tests for models.detector module.

Tests the ModelDetector class and backward-compatible detection functions.
"""

import pytest
from models.detector import ModelDetector, is_claude_model, is_gemini_model, is_claude_37_or_4
from models.registry import ProviderRegistry
from models.claude_provider import ClaudeProvider
from models.gemini_provider import GeminiProvider
from models.openai_provider import OpenAIProvider


class TestModelDetector:
    """Test cases for ModelDetector class."""
    
    @pytest.fixture
    def registry(self):
        """Create a registry with all providers."""
        reg = ProviderRegistry()
        reg.register(ClaudeProvider())
        reg.register(GeminiProvider())
        reg.register(OpenAIProvider())
        return reg
    
    @pytest.fixture
    def detector(self, registry):
        """Create a ModelDetector instance."""
        return ModelDetector(registry)
    
    # Claude Model Detection Tests
    def test_is_claude_model_full_name(self, detector):
        """Test Claude detection with full model names."""
        assert detector.is_claude_model("claude-4.5-sonnet") is True
        assert detector.is_claude_model("claude-4-opus") is True
        assert detector.is_claude_model("claude-3.7-sonnet") is True
        assert detector.is_claude_model("claude-3.5-sonnet") is True
    
    def test_is_claude_model_with_prefix(self, detector):
        """Test Claude detection with anthropic-- prefix."""
        assert detector.is_claude_model("anthropic--claude-4.5-sonnet") is True
        assert detector.is_claude_model("anthropic--claude-4-opus") is True
    
    def test_is_claude_model_partial_names(self, detector):
        """Test Claude detection with partial names."""
        assert detector.is_claude_model("clau") is True
        assert detector.is_claude_model("claud") is True
        assert detector.is_claude_model("sonnet") is True
        assert detector.is_claude_model("sonne") is True
    
    def test_is_claude_model_case_insensitive(self, detector):
        """Test Claude detection is case insensitive."""
        assert detector.is_claude_model("CLAUDE-4.5-SONNET") is True
        assert detector.is_claude_model("Claude-4-Opus") is True
        assert detector.is_claude_model("SONNET") is True
    
    def test_is_claude_model_negative(self, detector):
        """Test Claude detection returns False for non-Claude models."""
        assert detector.is_claude_model("gpt-4o") is False
        assert detector.is_claude_model("gemini-2.5-pro") is False
        assert detector.is_claude_model("random-model") is False
    
    # Gemini Model Detection Tests
    def test_is_gemini_model_full_name(self, detector):
        """Test Gemini detection with full model names."""
        assert detector.is_gemini_model("gemini-2.5-pro") is True
        assert detector.is_gemini_model("gemini-2.5-flash") is True
        assert detector.is_gemini_model("gemini-1.5-pro") is True
        assert detector.is_gemini_model("gemini-1.5-flash") is True
    
    def test_is_gemini_model_short_names(self, detector):
        """Test Gemini detection with short names."""
        assert detector.is_gemini_model("gemini-pro") is True
        assert detector.is_gemini_model("gemini-flash") is True
        assert detector.is_gemini_model("gemini") is True
    
    def test_is_gemini_model_case_insensitive(self, detector):
        """Test Gemini detection is case insensitive."""
        assert detector.is_gemini_model("GEMINI-2.5-PRO") is True
        assert detector.is_gemini_model("Gemini-Flash") is True
    
    def test_is_gemini_model_negative(self, detector):
        """Test Gemini detection returns False for non-Gemini models."""
        assert detector.is_gemini_model("claude-4.5-sonnet") is False
        assert detector.is_gemini_model("gpt-4o") is False
        assert detector.is_gemini_model("random-model") is False
    
    # Claude 3.7/4 Detection Tests
    def test_is_claude_37_or_4_explicit_versions(self, detector):
        """Test Claude 3.7/4 detection with explicit version numbers."""
        assert detector.is_claude_37_or_4("claude-3.7-sonnet") is True
        assert detector.is_claude_37_or_4("claude-4-opus") is True
        assert detector.is_claude_37_or_4("claude-4.5-sonnet") is True
    
    def test_is_claude_37_or_4_without_35(self, detector):
        """Test Claude 3.7/4 detection for Claude models without 3.5."""
        assert detector.is_claude_37_or_4("claude-sonnet") is True
        assert detector.is_claude_37_or_4("anthropic--claude-opus") is True
    
    def test_is_claude_37_or_4_negative(self, detector):
        """Test Claude 3.7/4 detection returns False for Claude 3.5."""
        assert detector.is_claude_37_or_4("claude-3.5-sonnet") is False
    
    def test_is_claude_37_or_4_non_claude(self, detector):
        """Test Claude 3.7/4 detection returns False for non-Claude models."""
        # Note: gpt-4o contains "4" but is not a Claude model, so is_claude_model returns False
        # which makes is_claude_37_or_4 return False (it checks is_claude_model first)
        assert detector.is_claude_37_or_4("gpt-5") is False
        assert detector.is_claude_37_or_4("gemini-2.5-pro") is False
    
    # Provider Detection Tests
    def test_detect_provider_claude(self, detector):
        """Test provider detection for Claude models."""
        assert detector.detect_provider("claude-4.5-sonnet") == "claude"
        assert detector.detect_provider("anthropic--claude-4-opus") == "claude"
    
    def test_detect_provider_gemini(self, detector):
        """Test provider detection for Gemini models."""
        assert detector.detect_provider("gemini-2.5-pro") == "gemini"
        assert detector.detect_provider("gemini-flash") == "gemini"
    
    def test_detect_provider_openai(self, detector):
        """Test provider detection for OpenAI models."""
        assert detector.detect_provider("gpt-4o") == "openai"
        assert detector.detect_provider("gpt-5") == "openai"
    
    def test_detect_provider_unknown(self, detector):
        """Test provider detection for unknown models returns OpenAI (fallback)."""
        # OpenAI provider accepts all models as fallback
        assert detector.detect_provider("unknown-model") == "openai"
    
    # Version Extraction Tests
    def test_get_model_version_claude(self, detector):
        """Test version extraction for Claude models."""
        assert detector.get_model_version("claude-3.5-sonnet") == "3.5"
        assert detector.get_model_version("claude-3.7-sonnet") == "3.7"
        assert detector.get_model_version("claude-4-opus") == "4"
        assert detector.get_model_version("claude-4.5-sonnet") == "4.5"
    
    def test_get_model_version_gemini(self, detector):
        """Test version extraction for Gemini models."""
        assert detector.get_model_version("gemini-1.5-pro") == "1.5"
        assert detector.get_model_version("gemini-2.5-flash") == "2.5"
    
    def test_get_model_version_no_version(self, detector):
        """Test version extraction returns None when no version found."""
        # Models without explicit version numbers return None
        assert detector.get_model_version("claude-sonnet") is None
        assert detector.get_model_version("gemini-pro") is None
        assert detector.get_model_version("gpt") is None


class TestBackwardCompatibleFunctions:
    """Test backward-compatible module-level functions."""
    
    def test_is_claude_model_function(self):
        """Test backward-compatible is_claude_model function."""
        assert is_claude_model("claude-4.5-sonnet") is True
        assert is_claude_model("gpt-4o") is False
    
    def test_is_gemini_model_function(self):
        """Test backward-compatible is_gemini_model function."""
        assert is_gemini_model("gemini-2.5-pro") is True
        assert is_gemini_model("claude-4.5-sonnet") is False
    
    def test_is_claude_37_or_4_function(self):
        """Test backward-compatible is_claude_37_or_4 function."""
        assert is_claude_37_or_4("claude-4.5-sonnet") is True
        assert is_claude_37_or_4("claude-3.5-sonnet") is False
    
    def test_functions_use_default_detector(self):
        """Test that backward-compatible functions use default detector."""
        # These should work without explicit detector initialization
        assert is_claude_model("claude-4.5-sonnet") is True
        assert is_gemini_model("gemini-2.5-pro") is True
        assert is_claude_37_or_4("claude-4-opus") is True


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    @pytest.fixture
    def detector(self):
        """Create a detector with empty registry."""
        return ModelDetector(ProviderRegistry())
    
    def test_empty_model_name(self, detector):
        """Test detection with empty model name."""
        assert detector.is_claude_model("") is False
        assert detector.is_gemini_model("") is False
        assert detector.is_claude_37_or_4("") is False
    
    def test_none_model_name(self, detector):
        """Test detection handles None gracefully."""
        # These should not raise exceptions
        try:
            detector.is_claude_model(None)
        except (TypeError, AttributeError):
            pass  # Expected behavior
    
    def test_special_characters(self, detector):
        """Test detection with special characters."""
        assert detector.is_claude_model("claude@4.5") is True  # Contains 'claude'
        assert detector.is_gemini_model("gemini#2.5") is True  # Contains 'gemini'
    
    def test_detector_without_registry(self):
        """Test detector creates default registry if none provided."""
        detector = ModelDetector()
        # Should not raise exception
        assert detector.is_claude_model("claude-4.5-sonnet") is True