## 1. Foundation - Converters Package Setup

- [ ] 1.1 Create `converters/` directory structure with `__init__.py`
- [ ] 1.2 Create `converters/mappings.py` with centralized stop reason mappings and API version constants
- [ ] 1.3 Create `converters/base.py` with `Converter` Protocol definition
- [ ] 1.4 Update existing code to import constants from `converters.mappings` (remove duplicates from `proxy_helpers.py`, `streaming_generators.py`, `streaming_handler.py`)

## 2. Extract Converters - OpenAI Module

- [ ] 2.1 Create `converters/openai.py` with `from_claude()` function (extract from `Converters.convert_claude_to_openai`)
- [ ] 2.2 Add `from_claude37()` function (extract from `Converters.convert_claude37_to_openai`)
- [ ] 2.3 Add `from_gemini()` function (extract from `Converters.convert_gemini_to_openai`)
- [ ] 2.4 Write unit tests for `converters/openai.py`

## 3. Extract Converters - Claude Module

- [ ] 3.1 Create `converters/claude.py` with `from_openai()` function (extract from `Converters.convert_openai_to_claude`)
- [ ] 3.2 Add `from_openai_messages()` function (extract from `Converters.convert_openai_messages_to_claude`)
- [ ] 3.3 Add `to_bedrock()` function (extract from `Converters.convert_claude_to_bedrock`)
- [ ] 3.4 Write unit tests for `converters/claude.py`

## 4. Extract Converters - Gemini Module

- [ ] 4.1 Create `converters/gemini.py` with `from_openai()` function (extract from `Converters.convert_openai_to_gemini`)
- [ ] 4.2 Add `from_claude()` function (extract from `Converters.convert_claude_to_gemini`)
- [ ] 4.3 Write unit tests for `converters/gemini.py`

## 5. Extract Converters - Chunks Module

- [ ] 5.1 Create `converters/chunks.py` with `claude_to_openai_chunk()` function
- [ ] 5.2 Add `claude37_to_openai_chunk()` function
- [ ] 5.3 Add `gemini_to_openai_chunk()` function
- [ ] 5.4 Write unit tests for `converters/chunks.py`

## 6. Update Facade and Exports

- [ ] 6.1 Update `converters/__init__.py` to re-export all converter functions
- [ ] 6.2 Update `proxy_helpers.py:Converters` to delegate to new modules (backward compatibility)
- [ ] 6.3 Verify all existing tests pass with delegation layer

## 7. Model Handler Registry

- [ ] 7.1 Create `handlers/registry.py` with `ModelHandlerRegistry` class and `ModelHandler` Protocol
- [ ] 7.2 Create `handlers/base_handler.py` with `DefaultHandler` implementation
- [ ] 7.3 Create `handlers/claude_handler.py` with `@ModelHandlerRegistry.register(Detector.is_claude_model)`
- [ ] 7.4 Create `handlers/gemini_handler.py` with `@ModelHandlerRegistry.register(Detector.is_gemini_model)`
- [ ] 7.5 Create `handlers/openai_handler.py` with `@ModelHandlerRegistry.register(Detector.is_openai_model)`
- [ ] 7.6 Write unit tests for registry and handlers

## 8. Integrate Model Handler Registry

- [ ] 8.1 Update `handlers/streaming_generators.py` to use `ModelHandlerRegistry.get_handler()`
- [ ] 8.2 Update `handlers/model_handlers.py` to use registry (or deprecate in favor of new handlers)
- [ ] 8.3 Update `load_balancer.py` to use handler-provided endpoints
- [ ] 8.4 Update `blueprints/chat_completions.py` to use registry
- [ ] 8.5 Update `blueprints/messages.py` to use registry
- [ ] 8.6 Verify all existing tests pass with registry

## 9. Dependency Injection - Flask App Context

- [ ] 9.1 Update `proxy_server.py:create_app()` to store `proxy_config` in `app.config['proxy_config']`
- [ ] 9.2 Update `proxy_server.py:create_app()` to store `proxy_ctx` in `app.config['proxy_ctx']`
- [ ] 9.3 Update `blueprints/chat_completions.py` to use `current_app.config` instead of globals
- [ ] 9.4 Update `blueprints/messages.py` to use `current_app.config` instead of globals
- [ ] 9.5 Update `blueprints/embeddings.py` to use `current_app.config` instead of globals
- [ ] 9.6 Remove `init_module()` functions from blueprints
- [ ] 9.7 Remove `_proxy_config` and `_ctx` global variables from blueprint modules

## 10. Cleanup and Verification

- [ ] 10.1 Remove duplicate stop reason mappings from `handlers/streaming_generators.py`
- [ ] 10.2 Remove duplicate stop reason mappings from `handlers/streaming_handler.py`
- [ ] 10.3 Remove duplicate API version constants from `handlers/model_handlers.py`
- [ ] 10.4 Run full test suite and verify 50%+ coverage target
- [ ] 10.5 Run integration tests to verify external API compatibility
- [ ] 10.6 Update inline documentation for new module structure
