# Tasks: Extract Routing Module

## 1. Directory Structure and Initial Setup
- [ ] 1.1 Create `routing/` directory
- [ ] 1.2 Create `routing/protocols/` directory
- [ ] 1.3 Create `routing/__init__.py`
- [ ] 1.4 Create `routing/protocols/__init__.py`
- [ ] 1.5 Run `lsp_diagnostics` to verify directory structure

## 2. Extract Strategy Module
- [ ] 2.1 Create `routing/strategy.py`
- [ ] 2.2 Create `LoadBalancingStrategy` abstract base class
- [ ] 2.3 Define abstract methods: `select_endpoint()`, `get_name()`
- [ ] 2.4 Create `RoundRobinStrategy` class with thread-safe counters
- [ ] 2.5 Create `LeastConnectionsStrategy` class (stub for future)
- [ ] 2.6 Create `WeightedStrategy` class (stub for future)
- [ ] 2.7 Add type hints for all strategy classes
- [ ] 2.8 Create `tests/routing/test_strategy.py`
- [ ] 2.9 Test strategy selection logic
- [ ] 2.10 Run `lsp_diagnostics` on `routing/strategy.py`

## 3. Extract Load Balancer Module
- [ ] 3.1 Create `routing/load_balancer.py`
- [ ] 3.2 Create `LoadBalancer` class
- [ ] 3.3 Extract model-to-subaccount mapping from `proxy_server.py:load_balance_url`
- [ ] 3.4 Extract subaccount-to-deployment-URL mapping from `proxy_server.py:load_balance_url`
- [ ] 3.5 Extract model fallback logic (Claude, Gemini, GPT fallbacks)
- [ ] 3.6 Implement `RoundRobinStrategy` integration with thread-safe counters
- [ ] 3.7 Add support for dynamic strategy selection
- [ ] 3.8 Ensure all counter operations use `threading.Lock`
- [ ] 3.9 Create `tests/routing/test_load_balancer.py`
- [ ] 3.10 Test round-robin selection across subaccounts
- [ ] 3.11 Test round-robin selection within subaccount (multiple URLs)
- [ ] 3.12 Test model fallback logic
- [ ] 3.13 Test thread-safety with concurrent load
- [ ] 3.14 Run `lsp_diagnostics` on `routing/load_balancer.py`

## 4. Extract Health and Circuit Breaker Module
- [ ] 4.1 Create `routing/health.py`
- [ ] 4.2 Create `CircuitBreaker` class
- [ ] 4.3 Implement failure counting with configurable threshold
- [ ] 4.4 Implement timeout tracking for failures
- [ ] 4.5 Implement half-open state for recovery attempts
- [ ] 4.6 Create `HealthChecker` class
- [ ] 4.7 Implement endpoint health check (HEAD request or simple timeout)
- [ ] 4.8 Integrate circuit breaker with load balancer
- [ ] 4.9 Add logging for circuit breaker state transitions
- [ ] 4.10 Create `tests/routing/test_health.py`
- [ ] 4.11 Test circuit breaker opens after threshold failures
- [ ] 4.12 Test circuit breaker closes after timeout
- [ ] 4.13 Test health check endpoint detection
- [ ] 4.14 Run `lsp_diagnostics` on `routing/health.py`

## 5. Extract Protocol Handlers
- [ ] 5.1 Create `routing/protocols/claude_converse.py`
- [ ] 5.2 Extract `/converse` endpoint logic from `handle_claude_request`
- [ ] 5.3 Extract `/converse-stream` endpoint logic
- [ ] 5.4 Integrate with `Converters.convert_openai_to_claude37`
- [ ] 5.5 Create `routing/protocols/claude_invoke.py`
- [ ] 5.6 Extract `/invoke` endpoint logic from `handle_claude_request`
- [ ] 5.7 Extract `/invoke-with-response-stream` endpoint logic
- [ ] 5.8 Integrate with `Converters.convert_openai_to_claude`
- [ ] 5.9 Create `routing/protocols/gemini_generate.py`
- [ ] 5.10 Extract `/generateContent` endpoint logic from `handle_gemini_request`
- [ ] 5.11 Extract `/streamGenerateContent` endpoint logic
- [ ] 5.12 Integrate with `Converters.convert_openai_to_gemini`
- [ ] 5.13 Create `routing/protocols/openai_chat.py`
- [ ] 5.14 Extract `/chat/completions` endpoint logic from `handle_default_request`
- [ ] 5.15 Extract API version selection logic (2023-05-15 vs 2024-12-01-preview)
- [ ] 5.16 Create `tests/routing/protocols/test_claude_converse.py`
- [ ] 5.17 Create `tests/routing/protocols/test_claude_invoke.py`
- [ ] 5.18 Create `tests/routing/protocols/test_gemini_generate.py`
- [ ] 5.19 Create `tests/routing/protocols/test_openai_chat.py`
- [ ] 5.20 Test endpoint path construction for all protocols
- [ ] 5.21 Test streaming vs non-streaming endpoint selection
- [ ] 5.22 Run `lsp_diagnostics` on all protocol handler files

## 6. Extract Request Router
- [ ] 6.1 Create `routing/request_router.py`
- [ ] 6.2 Create `RequestRouter` class
- [ ] 6.3 Implement model detection using `Detector` from proxy_helpers
- [ ] 6.4 Implement protocol selection logic (Claude 3.7/4 vs 3.5, Gemini, OpenAI)
- [ ] 6.5 Integrate `LoadBalancer` for endpoint selection
- [ ] 6.6 Integrate `CircuitBreaker` for failover
- [ ] 6.7 Implement dynamic converter selection based on protocol
- [ ] 6.8 Add logging for routing decisions (model, protocol, endpoint)
- [ ] 6.9 Create `tests/routing/test_request_router.py`
- [ ] 6.10 Test routing for Claude 3.5 models
- [ ] 6.11 Test routing for Claude 3.7/4 models
- [ ] 6.12 Test routing for Gemini models
- [ ] 6.13 Test routing for OpenAI models
- [ ] 6.14 Test model fallback scenarios
- [ ] 6.15 Test failover scenarios with circuit breaker
- [ ] 6.16 Run `lsp_diagnostics` on `routing/request_router.py`

## 7. Create Routing Public API
- [ ] 7.1 Implement `routing/__init__.py` with all imports
- [ ] 7.2 Re-export `LoadBalancer`, `RequestRouter`, `CircuitBreaker` classes
- [ ] 7.3 Re-export all strategy classes
- [ ] 7.4 Re-export all protocol handler classes
- [ ] 7.5 Create facade function `load_balance_url()` (backward compatibility)
- [ ] 7.6 Create facade function `route_request()` (backward compatibility)
- [ ] 7.7 Define `__all__` list with all public exports
- [ ] 7.8 Add deprecation warnings for old API (if applicable)
- [ ] 7.9 Run `lsp_diagnostics` on `routing/__init__.py`

## 8. Update proxy_server.py
- [ ] 8.1 Replace `load_balance_url` import with routing module
- [ ] 8.2 Remove `load_balance_url()` function from proxy_server.py
- [ ] 8.3 Update `handle_claude_request()` to use `RequestRouter`
- [ ] 8.4 Update `handle_gemini_request()` to use `RequestRouter`
- [ ] 8.5 Update `handle_default_request()` to use `RequestRouter`
- [ ] 8.6 Verify all routing logic preserved
- [ ] 8.7 Run `lsp_diagnostics` on `proxy_server.py`

## 9. Testing and Validation
- [ ] 9.1 Run all existing tests (295+ tests)
- [ ] 9.2 Verify all tests pass
- [ ] 9.3 Run `make test-cov` to check coverage
- [ ] 9.4 Verify >90% coverage on `routing/` module
- [ ] 9.5 Run integration tests for `/v1/chat/completions` endpoint
- [ ] 9.6 Run integration tests for `/v1/messages` endpoint
- [ ] 9.7 Run integration streaming tests
- [ ] 9.8 Verify `proxy_server.py` line count reduced by ~200+
- [ ] 9.9 Verify thread-safety with concurrent load tests
- [ ] 9.10 Test health check and circuit breaker functionality
- [ ] 9.11 Test failover scenarios
- [ ] 9.12 Verify routing with all supported model providers
- [ ] 9.13 Check for circular import warnings
- [ ] 9.14 Verify no import errors in any module

## 10. Documentation
- [ ] 10.1 Update `ARCHITECTURE.md` to reflect new module structure
- [ ] 10.2 Update routing documentation in README
- [ ] 10.3 Add docstrings to all new routing modules
- [ ] 10.4 Verify all public APIs have proper type hints
- [ ] 10.5 Update `PYTHON_CONVENTIONS.md` if needed
