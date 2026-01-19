# Design: Extract Routing Module

## Context

The SAP AI Core LLM Proxy has successfully extracted authentication, configuration, and converter modules in previous phases. However, routing logic remains embedded in `proxy_server.py`, mixing load balancing, model detection, endpoint selection, and format conversion concerns.

This change extracts routing logic into a dedicated `routing/` module with support for algorithm transforming, dynamic converter choice, load balancing, and failover.

### Current Problems

1. **Monolithic routing in proxy_server.py**: Load balancing, endpoint selection, and converter choice are mixed together in handler functions
2. **Thread-safety issue**: `load_balance_url.counters` is accessed without locks, causing race conditions
3. **Hardcoded load balancing**: Only round-robin is supported; no extensibility for other algorithms
4. **No failover mechanism**: No health checks or circuit breakers to handle unavailable endpoints
5. **Tight coupling**: Routing handlers (`handle_claude_request`, `handle_gemini_request`) are tightly coupled to specific converter logic
6. **Poor testability**: Load balancing and routing logic cannot be unit tested in isolation

### Constraints

- Must maintain backward compatibility with existing API
- No external dependencies added (use existing Python stdlib and project dependencies)
- Must preserve existing routing behavior (round-robin, model fallbacks)
- Must maintain thread-safety for high-concurrency scenarios
- All existing tests must continue to pass

## Goals / Non-Goals

### Goals

1. **Modular Routing Architecture**: Separate routing concerns into focused, single-purpose modules
2. **Strategy Pattern for Load Balancing**: Support multiple algorithms (round-robin, least-connections, weighted)
3. **Health Checks and Failover**: Detect unavailable endpoints and automatically failover
4. **Dynamic Converter Selection**: Choose converters based on model detection and endpoint protocol
5. **Thread-Safe Operations**: Proper locking for all shared state
6. **Improved Testability**: Each routing module can be unit tested independently
7. **High Test Coverage**: >90% coverage on `routing/` module
8. **Backward Compatibility**: Existing API continues to work without changes

### Non-Goals

- Changing load balancing default behavior (preserve round-robin)
- Adding new routing algorithms beyond strategy pattern infrastructure
- Changing converter API signatures (maintain existing behavior)
- Performance optimization (focus on modularity and reliability)
- Implementing plugin architecture (future work)

## Decisions

### 1. Load Balancing: Strategy Pattern with Thread-Safety

**Decision**: Implement `LoadBalancer` abstract base class with concrete strategies (`RoundRobinStrategy`, `LeastConnectionsStrategy`, `WeightedStrategy`), all with thread-safe counters.

**Rationale**:
- Strategy pattern allows easy addition of new algorithms without changing core logic
- Thread-safety prevents race conditions in high-concurrency scenarios
- Clear separation between balancing algorithm and endpoint selection
- Each strategy can be unit tested independently

**Alternatives Considered**:
- Factory pattern with function-based strategies:
  - Pros: Simpler
  - Cons: No type safety, harder to manage state
- Single monolithic function with algorithm parameter:
  - Pros: Minimal code
  - Cons: Violates Open/Closed Principle, hard to extend

### 2. Protocol Handlers: Separate Classes per API Protocol

**Decision**: Create protocol handler classes in `routing/protocols/` (`ClaudeConverseProtocol`, `ClaudeInvokeProtocol`, `GeminiGenerateProtocol`, `OpenAIChatProtocol`).

**Rationale**:
- Encapsulates protocol-specific logic (endpoint paths, converter choice, response parsing)
- Each protocol can be tested independently
- Easy to add new protocols (e.g., future API versions)
- Clear separation of concerns between routing and protocol handling

**Alternatives Considered**:
- Protocol registry with function callbacks:
  - Pros: Simpler registration
  - Cons: Harder to maintain state, less type-safe
- Inline protocol logic in request router:
  - Pros: Fewer files
  - Cons: Violates SRP, large complex functions

### 3. Request Router: Unified Routing Decision Tree

**Decision**: Create `RequestRouter` class that orchestrates model detection → load balancing → protocol selection → endpoint construction.

**Rationale**:
- Single entry point for all routing decisions
- Clear pipeline: Detect → Balance → Select Protocol → Build Endpoint
- Easier to debug and trace routing decisions
- Enables request-scoped logging and metrics

**Alternatives Considered**:
- Keep routing in handler functions:
  - Pros: No change to existing handlers
  - Cons: Duplicated logic, hard to test
- Dispatcher pattern with multiple routers:
  - Pros: Separation by model type
  - Cons: More complex orchestration, harder to maintain

### 4. Health Checks: Circuit Breaker Pattern

**Decision**: Implement `CircuitBreaker` class with failure counting, timeout, and half-open state for automatic failover.

**Rationale**:
- Prevents cascading failures by avoiding unhealthy endpoints
- Automatic recovery with half-open state
- Industry-standard pattern for resilience
- Configurable thresholds (failure count, timeout, recovery time)

**Alternatives Considered**:
- Simple retry only (no circuit breaker):
  - Pros: Simpler
  - Cons: No protection against degraded endpoints
- Health check endpoint polling:
  - Pros: Proactive detection
  - Cons: Adds network overhead, complex to implement

### 5. Backward Compatibility: Facade Pattern

**Decision**: Create `routing/__init__.py` with facade functions that maintain existing API signatures.

**Rationale**:
- Existing code continues to work without changes
- Gradual migration path (facade → direct imports)
- Clear separation between implementation and public API
- Low risk - minimal code change

**Alternatives Considered**:
- Replace all imports immediately:
  - Pros: Clean break
  - Cons: Breaking change, requires updating all callers
- Alias module (import routing as proxy_routing):
  - Pros: Zero code duplication
  - Cons: Confusing for debugging, unclear migration path

## Dependencies

### Internal Dependencies

```
routing/load_balancer.py
  └─→ config/ (ProxyConfig, SubAccountConfig)

routing/request_router.py
  ├─→ routing/load_balancer.py
  ├─→ routing/protocols/
  ├─→ proxy_helpers.py (Detector, Converters)
  └─→ routing/health.py

routing/protocols/*.py
  ├─→ proxy_helpers.py (Detector, Converters)
  └─→ routing/health.py

routing/health.py
  └─→ routing/load_balancer.py

routing/strategy.py
  └─→ (No internal dependencies)
```

### External Dependencies (No New Dependencies)

- `threading`: Python stdlib (for thread-safety)
- `logging`: Python stdlib
- `dataclasses`: Python stdlib
- `typing`: Python stdlib
- `abc`: Python stdlib (for abstract base classes)
- `time`: Python stdlib (for health check timeouts)

### Import Ordering

To avoid circular dependencies:
1. `routing/strategy.py` - No internal dependencies
2. `routing/load_balancer.py` - Depends on strategy.py
3. `routing/health.py` - Depends on load_balancer.py
4. `routing/protocols/*.py` - Depend on health.py, proxy_helpers.py
5. `routing/request_router.py` - Depends on all above modules
6. `routing/__init__.py` - Re-exports all modules

## Migration Plan

### Phase-by-Phase Extraction

| Phase | Task | Effort | Files Created/Modified |
|-------|------|--------|------------------------|
| **1** | Create `routing/` directory structure & `__init__.py` files | 0.5d | 6 `__init__.py` files |
| **2** | Extract `strategy.py` (abstract base classes) | 0.5d | 1 file |
| **3** | Extract `load_balancer.py` (load balancing strategies) | 1.5d | 1 file |
| **4** | Extract `health.py` (circuit breaker, health checks) | 1d | 1 file |
| **5** | Extract `routing/protocols/` (protocol handlers) | 1.5d | 4 files |
| **6** | Extract `request_router.py` (unified routing) | 1d | 1 file |
| **7** | Create `routing/__init__.py` facade | 0.5d | 1 file |
| **8** | Update `proxy_server.py` to use new routing module | 1d | 1 file modified |
| **9** | Add/update unit tests | 1d | ~8 test files |

**Total Estimated Effort: 8 days**

### Rollback Plan

If issues arise during extraction:

1. **Phase-level rollback**: Each phase is independent; revert to specific phase's commits
2. **Full rollback**: Facade in `routing/__init__.py` ensures existing routing continues working
3. **Feature flag**: Add `USE_LEGACY_ROUTING=true` env var to fall back to old code (optional)

### Validation Strategy

**After Each Phase:**
- Run existing test suite to ensure no regressions
- Run `lsp_diagnostics` on modified files
- Verify imports resolve correctly

**After Phase 9:**
- All existing tests pass
- New unit tests achieve >90% coverage on `routing/` module
- Integration tests verify routing with all providers (Claude, Gemini, OpenAI)
- `proxy_server.py` reduced by ~200 lines
- Thread-safety verified with concurrent load tests
- Health checks and circuit breaker work correctly

## Risks / Trade-offs

### Risk 1: Import Cycles

**Probability**: Medium
**Impact**: High

**Mitigation**:
- Careful dependency ordering (see Dependencies section above)
- Use `TYPE_CHECKING` for forward type hints
- Module-level imports at top, not inside functions
- Test imports with circular import detection tool

**Trade-off**:
- More complex import structure vs. clean separation of concerns

### Risk 2: Routing Behavior Changes

**Probability**: Low
**Impact**: High

**Mitigation**:
- Comprehensive integration tests for all routing scenarios
- Preserve exact round-robin algorithm logic
- Preserve model fallback behavior
- Detailed logging for routing decisions

**Trade-off**:
- Increased testing effort vs. confidence in routing correctness

### Risk 3: Thread-Safety Bugs

**Probability**: Medium
**Impact**: High

**Mitigation**:
- Use `threading.Lock` for all shared state
- Unit tests with concurrent load testing
- Static analysis tools (mypy) for race condition detection
- Stress testing under high load

**Trade-off**:
- Performance overhead from locks vs. thread-safety guarantees

### Risk 4: Backward Compatibility Breaks

**Probability**: Low
**Impact**: Medium

**Mitigation**:
- Facade layer with direct delegation
- Integration tests verify all existing routing patterns
- Keep facade API identical to old behavior

**Trade-off**:
- Extra facade code vs. zero breaking changes

## Open Questions

1. **Should we add `USE_LEGACY_ROUTING` feature flag?**
   - Decision: Optional, add only if migration issues arise
   - Rationale: Adds complexity; facade should be sufficient

2. **Should we expose load balancing algorithm configuration via config.json?**
   - Decision: No, keep as environment variable or future config enhancement
   - Rationale: Adds complexity to config schema; current scope is extraction only

3. **Should we implement weighted load balancing now?**
   - Decision: No, implement strategy infrastructure only
   - Rationale: No clear use case yet; implement when needed

4. **Should we create routing metrics collection?**
   - Decision: No, out of scope for this change
   - Rationale: Add in future enhancement focused on observability

## Success Criteria

- [ ] All existing tests pass
- [ ] New unit tests achieve >90% coverage on `routing/` module
- [ ] `proxy_server.py` reduced by ~200 lines
- [ ] Load balancer counters are thread-safe (verified with concurrent load tests)
- [ ] Health checks detect unavailable endpoints
- [ ] Circuit breaker prevents cascading failures
- [ ] Failover to alternative endpoints works automatically
- [ ] Round-robin load balancing behavior preserved
- [ ] Model fallback mechanism preserved
- [ ] Protocol handlers correctly select converters
- [ ] No circular import warnings
- [ ] Routing with all providers works (Claude, Gemini, OpenAI)
- [ ] Backward compatibility maintained via facade
