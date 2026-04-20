"""Unit tests for utils/model_aliases.py.

Tests cover:
- DEFAULT_ALIASES contents and completeness
- resolve_model_name: exact match, case-insensitive, no alias
- load_aliases_from_file: file found, missing, malformed
"""

import json
import pytest
from pathlib import Path

from utils.model_aliases import (
    DEFAULT_ALIASES,
    resolve_model_name,
    load_aliases_from_file,
)


class TestDefaultAliases:
    def test_aliases_is_dict(self):
        assert isinstance(DEFAULT_ALIASES, dict)
        assert len(DEFAULT_ALIASES) > 0

    def test_all_values_are_strings(self):
        for key, val in DEFAULT_ALIASES.items():
            assert isinstance(key, str), f"Key '{key}' is not a string"
            assert isinstance(val, str), f"Value '{val}' for key '{key}' is not a string"

    def test_known_anthropic_aliases(self):
        assert DEFAULT_ALIASES.get("claude-3.5-sonnet") == "anthropic--claude-3.5-sonnet"
        assert DEFAULT_ALIASES.get("claude-3.7-sonnet") == "anthropic--claude-3.7-sonnet"

    def test_known_openai_aliases(self):
        assert DEFAULT_ALIASES.get("gpt-4") == "gpt-4o"

    def test_known_gemini_aliases(self):
        assert DEFAULT_ALIASES.get("gemini-pro") == "gemini-2.5-pro"

    def test_known_amazon_aliases(self):
        assert DEFAULT_ALIASES.get("nova-lite") == "amazon--nova-lite"

    def test_known_mistral_aliases(self):
        assert DEFAULT_ALIASES.get("mistral-large") == "mistralai--mistral-large-instruct"


class TestResolveModelName:
    def test_exact_match(self):
        assert resolve_model_name("claude-3.5-sonnet") == "anthropic--claude-3.5-sonnet"

    def test_exact_match_already_canonical(self):
        # A canonical name passed directly should pass through
        # (if it's not in DEFAULT_ALIASES, it returns unchanged)
        result = resolve_model_name("anthropic--claude-4.5-sonnet")
        assert result == "anthropic--claude-4.5-sonnet"

    def test_case_insensitive_match(self):
        # "gpt-4" is in DEFAULT_ALIASES as lowercase; "GPT-4" should still resolve
        result = resolve_model_name("GPT-4")
        assert result == "gpt-4o"

    def test_no_alias_returns_original(self):
        # A model name not in any alias map is returned unchanged
        result = resolve_model_name("totally-unknown-model-xyz")
        assert result == "totally-unknown-model-xyz"

    def test_custom_aliases_override(self):
        custom = {"my-model": "canonical-name-v2"}
        result = resolve_model_name("my-model", aliases=custom)
        assert result == "canonical-name-v2"

    def test_custom_aliases_no_default_bleed(self):
        # When custom aliases provided, DEFAULT_ALIASES not used
        custom = {"my-model": "canonical-name-v2"}
        # "claude-3.5-sonnet" is in DEFAULT_ALIASES but not custom
        result = resolve_model_name("claude-3.5-sonnet", aliases=custom)
        # Should return unchanged since not in custom aliases
        assert result == "claude-3.5-sonnet"

    def test_none_aliases_uses_defaults(self):
        result = resolve_model_name("claude-3.5-sonnet", aliases=None)
        assert result == "anthropic--claude-3.5-sonnet"

    def test_gemini_alias(self):
        result = resolve_model_name("gemini-flash")
        assert result == "gemini-2.5-flash"


class TestLoadAliasesFromFile:
    def test_loads_valid_file(self, tmp_path):
        aliases_file = tmp_path / "aliases.json"
        aliases_file.write_text(json.dumps({"my-model": "canonical-model"}))

        result = load_aliases_from_file(str(aliases_file))
        assert result["my-model"] == "canonical-model"
        # Defaults are preserved
        assert "claude-3.5-sonnet" in result

    def test_file_overrides_defaults(self, tmp_path):
        aliases_file = tmp_path / "aliases.json"
        # Override a default alias
        aliases_file.write_text(json.dumps({"claude-3.5-sonnet": "override-model"}))

        result = load_aliases_from_file(str(aliases_file))
        assert result["claude-3.5-sonnet"] == "override-model"

    def test_missing_file_returns_defaults(self, tmp_path):
        missing = str(tmp_path / "nonexistent.json")
        result = load_aliases_from_file(missing)
        # Returns DEFAULT_ALIASES when file is missing
        assert result == DEFAULT_ALIASES

    def test_malformed_json_returns_defaults(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json{{")

        result = load_aliases_from_file(str(bad_file))
        assert result == DEFAULT_ALIASES

    def test_non_dict_json_returns_defaults(self, tmp_path):
        array_file = tmp_path / "array.json"
        array_file.write_text(json.dumps(["not", "a", "dict"]))

        result = load_aliases_from_file(str(array_file))
        assert result == DEFAULT_ALIASES

    def test_custom_base_aliases(self, tmp_path):
        aliases_file = tmp_path / "aliases.json"
        aliases_file.write_text(json.dumps({"file-model": "file-canonical"}))

        base = {"base-model": "base-canonical"}
        result = load_aliases_from_file(str(aliases_file), base_aliases=base)
        assert result["base-model"] == "base-canonical"
        assert result["file-model"] == "file-canonical"
