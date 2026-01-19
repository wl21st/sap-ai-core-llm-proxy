# Tasks: Extract Converters Module

## 1. Directory Structure and Initial Setup
- [ ] 1.1 Create `converters/` directory
- [ ] 1.2 Create `converters/request/` directory
- [ ] 1.3 Create `converters/response/` directory
- [ ] 1.4 Create `converters/streaming/` directory
- [ ] 1.5 Create `converters/__init__.py`
- [ ] 1.6 Create `converters/request/__init__.py`
- [ ] 1.7 Create `converters/response/__init__.py`
- [ ] 1.8 Create `converters/streaming/__init__.py`
- [ ] 1.9 Run `lsp_diagnostics` to verify directory structure

## 2. Extract Mappings Module
- [ ] 2.1 Create `converters/mappings.py` with API version constants
- [ ] 2.2 Create `StopReasonMapper` class with bidirectional mappings
- [ ] 2.3 Add `claude_to_openai()`, `openai_to_claude()`, `gemini_to_openai()` methods
- [ ] 2.4 Extract stop reason dictionaries from `proxy_helpers.py`
- [ ] 2.5 Run unit tests to verify mapping correctness
- [ ] 2.6 Run `lsp_diagnostics` on `converters/mappings.py`

## 3. Extract Detector Module
- [ ] 3.1 Create `converters/detector.py`
- [ ] 3.2 Extract `Detector` class from `proxy_helpers.py:11-76`
- [ ] 3.3 Extract `CLAUDE_PREFIXES`, `CLAUDE_KEYWORDS`, `GEMINI_PREFIXES` constants
- [ ] 3.4 Extract `CLAUDE_37_4_PATTERNS` constant
- [ ] 3.5 Extract `is_claude_model()` static method
- [ ] 3.6 Extract `is_claude_37_or_4()` static method
- [ ] 3.7 Extract `is_gemini_model()` static method
- [ ] 3.8 Create `tests/converters/test_detector.py` with model detection tests
- [ ] 3.9 Run detector unit tests
- [ ] 3.10 Run `lsp_diagnostics` on `converters/detector.py`

## 4. Extract Reasoning Module
- [ ] 4.1 Create `converters/reasoning.py`
- [ ] 4.2 Extract thinking/budget_tokens adjustment from `proxy_server.py:1008-1082`
- [ ] 4.3 Create `ReasoningConfig` class
- [ ] 4.4 Add `UNSUPPORTED_THINKING_FIELDS` constant
- [ ] 4.5 Implement `adjust_for_claude()` static method
- [ ] 4.6 Implement `passthrough_reasoning_effort()` static method
- [ ] 4.7 Create `tests/converters/test_reasoning.py`
- [ ] 4.8 Test budget token adjustment logic
- [ ] 4.9 Test reasoning_effort passthrough
- [ ] 4.10 Run `lsp_diagnostics` on `converters/reasoning.py`

## 5. Extract Token Usage Module
- [ ] 5.1 Create `converters/token_usage.py`
- [ ] 5.2 Extract token extraction from `proxy_server.py:1633-1648` (non-streaming)
- [ ] 5.3 Extract token extraction from `proxy_server.py:1786-1798` (Claude 3.7 streaming)
- [ ] 5.4 Extract token extraction from `proxy_server.py:1931-1944` (Gemini usageMetadata)
- [ ] 5.5 Create `TokenUsage` dataclass with unified representation
- [ ] 5.6 Create `TokenExtractor` class
- [ ] 5.7 Implement `from_openai_response()` static method
- [ ] 5.8 Implement `from_claude_response()` static method
- [ ] 5.9 Implement `from_claude37_metadata()` static method
- [ ] 5.10 Implement `from_gemini_usage_metadata()` static method
- [ ] 5.11 Create `tests/converters/test_token_usage.py`
- [ ] 5.12 Test extraction from all response formats
- [ ] 5.13 Run `lsp_diagnostics` on `converters/token_usage.py`

## 6. Extract Request Converters
- [ ] 6.1 Create `converters/request/openai_to_claude.py`
- [ ] 6.2 Extract `convert_openai_to_claude()` from `proxy_helpers.py:88-108`
- [ ] 6.3 Extract `convert_openai_to_claude37()` from `proxy_helpers.py:110-238`
- [ ] 6.4 Create `converters/request/openai_to_gemini.py`
- [ ] 6.5 Extract `convert_openai_to_gemini()` from `proxy_helpers.py:874-1019`
- [ ] 6.6 Create `converters/request/claude_to_openai.py`
- [ ] 6.7 Extract `convert_claude_request_to_openai()` from `proxy_helpers.py:240-285`
- [ ] 6.8 Create `converters/request/claude_to_gemini.py`
- [ ] 6.9 Extract `convert_claude_request_to_gemini()` from `proxy_helpers.py:287-366`
- [ ] 6.10 Create `converters/request/claude_to_bedrock.py`
- [ ] 6.11 Extract `convert_claude_request_for_bedrock()` from `proxy_helpers.py:368-440`
- [ ] 6.12 Create `tests/converters/request/test_openai_to_claude.py`
- [ ] 6.13 Create `tests/converters/request/test_openai_to_gemini.py`
- [ ] 6.14 Create `tests/converters/request/test_claude_to_openai.py`
- [ ] 6.15 Create `tests/converters/request/test_claude_to_gemini.py`
- [ ] 6.16 Run request converter unit tests
- [ ] 6.17 Run `lsp_diagnostics` on all request converter files

## 7. Extract Response Converters
- [ ] 7.1 Create `converters/response/claude_to_openai.py`
- [ ] 7.2 Extract `convert_claude_to_openai()` from `proxy_helpers.py:442-502`
- [ ] 7.3 Extract `convert_claude37_to_openai()` from `proxy_helpers.py:504-684`
- [ ] 7.4 Create `converters/response/gemini_to_openai.py`
- [ ] 7.5 Extract `convert_gemini_to_openai()` from `proxy_helpers.py:1021-1130`
- [ ] 7.6 Create `converters/response/gemini_to_claude.py`
- [ ] 7.7 Extract `convert_gemini_response_to_claude()` from `proxy_helpers.py:1132-1206`
- [ ] 7.8 Create `converters/response/openai_to_claude.py`
- [ ] 7.9 Extract `convert_openai_response_to_claude()` from `proxy_helpers.py:1208-1305`
- [ ] 7.10 Create `tests/converters/response/test_claude_to_openai.py`
- [ ] 7.11 Create `tests/converters/response/test_gemini_to_openai.py`
- [ ] 7.12 Create `tests/converters/response/test_gemini_to_claude.py`
- [ ] 7.13 Create `tests/converters/response/test_openai_to_claude.py`
- [ ] 7.14 Run response converter unit tests
- [ ] 7.15 Run `lsp_diagnostics` on all response converter files

## 8. Extract Streaming Chunk Converters
- [ ] 8.1 Create `converters/streaming/claude_chunks.py`
- [ ] 8.2 Extract `convert_claude_chunk_to_openai()` from `proxy_helpers.py:686-717`
- [ ] 8.3 Extract `convert_claude37_chunk_to_openai()` from `proxy_helpers.py:719-872`
- [ ] 8.4 Create `converters/streaming/gemini_chunks.py`
- [ ] 8.5 Extract `convert_gemini_chunk_to_claude_delta()` from `proxy_helpers.py:1307-1322`
- [ ] 8.6 Extract `convert_gemini_chunk_to_openai()` from `proxy_helpers.py:1338-1431`
- [ ] 8.7 Create `converters/streaming/openai_chunks.py`
- [ ] 8.8 Extract `convert_openai_chunk_to_claude_delta()` from `proxy_helpers.py:1324-1336`
- [ ] 8.9 Create `tests/converters/streaming/test_claude_chunks.py`
- [ ] 8.10 Create `tests/converters/streaming/test_gemini_chunks.py`
- [ ] 8.11 Create `tests/converters/streaming/test_openai_chunks.py`
- [ ] 8.12 Run streaming chunk converter unit tests
- [ ] 8.13 Run `lsp_diagnostics` on all streaming chunk converter files

## 9. Extract Streaming Generators
- [ ] 9.1 Create `converters/streaming/generators.py`
- [ ] 9.2 Extract `generate_streaming_response()` from `proxy_server.py:1688-2189`
- [ ] 9.3 Extract `generate_claude_streaming_response()` from `proxy_server.py:2192-2500+`
- [ ] 9.4 Create `RequestContext` dataclass for request context encapsulation
- [ ] 9.5 Update imports to use `converters.detector`, `converters.mappings`, `converters.token_usage`
- [ ] 9.6 Update imports to use streaming chunk converters
- [ ] 9.7 Create `tests/converters/streaming/test_generators.py`
- [ ] 9.8 Test streaming response generation for all providers
- [ ] 9.9 Test streaming with Claude 3.5 models
- [ ] 9.10 Test streaming with Claude 3.7/4 models
- [ ] 9.11 Test streaming with Gemini models
- [ ] 9.12 Run `lsp_diagnostics` on `converters/streaming/generators.py`

## 10. Create Converters Public API
- [ ] 10.1 Implement `converters/__init__.py` with all imports
- [ ] 10.2 Re-export Detector, StopReasonMapper, ReasoningConfig classes
- [ ] 10.3 Re-export TokenUsage, TokenExtractor classes
- [ ] 10.4 Re-export all request converter functions
- [ ] 10.5 Re-export all response converter functions
- [ ] 10.6 Re-export all streaming converter functions
- [ ] 10.7 Create `Converters` class with static method delegates
- [ ] 10.8 Implement `Converters.convert_openai_to_claude` delegate
- [ ] 10.9 Implement `Converters.convert_openai_to_claude37` delegate
- [ ] 10.10 Implement `Converters.convert_openai_to_gemini` delegate
- [ ] 10.11 Implement `Converters.convert_claude_request_to_openai` delegate
- [ ] 10.12 Implement `Converters.convert_claude_request_to_gemini` delegate
- [ ] 10.13 Implement `Converters.convert_claude_request_for_bedrock` delegate
- [ ] 10.14 Implement `Converters.convert_claude_to_openai` delegate
- [ ] 10.15 Implement `Converters.convert_claude37_to_openai` delegate
- [ ] 10.16 Implement `Converters.convert_gemini_to_openai` delegate
- [ ] 10.17 Implement `Converters.convert_gemini_response_to_claude` delegate
- [ ] 10.18 Implement `Converters.convert_openai_response_to_claude` delegate
- [ ] 10.19 Implement `Converters.convert_claude_chunk_to_openai` delegate
- [ ] 10.20 Implement `Converters.convert_claude37_chunk_to_openai` delegate
- [ ] 10.21 Implement `Converters.convert_gemini_chunk_to_openai` delegate
- [ ] 10.22 Implement `Converters.convert_gemini_chunk_to_claude_delta` delegate
- [ ] 10.23 Implement `Converters.convert_openai_chunk_to_claude_delta` delegate
- [ ] 10.24 Re-export `generate_streaming_response` and `generate_claude_streaming_response`
- [ ] 10.25 Re-export `RequestContext` dataclass
- [ ] 10.26 Define `__all__` list with all public exports
- [ ] 10.27 Run `lsp_diagnostics` on `converters/__init__.py`

## 11. Update proxy_helpers.py Facade
- [ ] 11.1 Replace entire `proxy_helpers.py` content with facade code
- [ ] 11.2 Add deprecation warning on import
- [ ] 11.3 Import `Converters` and `Detector` from `converters` module
- [ ] 11.4 Define `__all__ = ["Detector", "Converters"]`
- [ ] 11.5 Verify facade works by importing `from proxy_helpers import Converters`
- [ ] 11.6 Verify deprecation warning is issued
- [ ] 11.7 Run `lsp_diagnostics` on `proxy_helpers.py`

## 12. Update proxy_server.py Imports
- [ ] 12.1 Replace `from proxy_helpers import Detector` with `from converters.detector import Detector`
- [ ] 12.2 Replace converter imports from `proxy_helpers.Converters` with `converters` module
- [ ] 12.3 Update `generate_streaming_response()` calls to use new module path
- [ ] 12.4 Update `generate_claude_streaming_response()` calls to use new module path
- [ ] 12.5 Update chunk converter imports to use new module paths
- [ ] 12.6 Update reasoning config imports to use `converters.reasoning`
- [ ] 12.7 Update token usage imports to use `converters.token_usage`
- [ ] 12.8 Run `lsp_diagnostics` on `proxy_server.py`
- [ ] 12.9 Run full test suite to verify no regressions
- [ ] 12.10 Verify streaming generators work for all models

## 13. Final Testing and Validation
- [ ] 13.1 Run all existing tests (295+ tests)
- [ ] 13.2 Verify all tests pass
- [ ] 13.3 Run `make test-cov` to check coverage
- [ ] 13.4 Verify >90% coverage on `converters/` module
- [ ] 13.5 Run integration tests for `/v1/chat/completions` endpoint
- [ ] 13.6 Run integration tests for `/v1/messages` endpoint
- [ ] 13.7 Run integration streaming tests
- [ ] 13.8 Verify `proxy_server.py` line count reduced by ~800+
- [ ] 13.9 Verify `proxy_helpers.py` line count <50
- [ ] 13.10 Check for circular import warnings
- [ ] 13.11 Verify no import errors in any module
- [ ] 13.12 Test with all supported model providers (Claude 3.5, 3.7/4, Gemini, OpenAI)
- [ ] 13.13 Verify deprecation warnings from `proxy_helpers` import

## 14. Documentation
- [ ] 14.1 Update `ARCHITECTURE.md` to reflect new module structure
- [ ] 14.2 Update import examples in README to use `converters` module
- [ ] 14.3 Add docstrings to all new converter modules
- [ ] 14.4 Verify all public APIs have proper type hints
- [ ] 14.5 Update `PYTHON_CONVENTIONS.md` if needed
