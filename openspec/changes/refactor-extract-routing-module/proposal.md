# Change: Extract Routing Module

## Why

The current routing logic is tightly coupled within `proxy_server.py`, mixing load balancing, model detection, endpoint selection, and format conversion concerns. The `load_balance_url()` function uses hierarchical round-robin without thread-safety, and routing decisions are scattered across multiple handler functions (`handle_claude_request`, `handle_gemini_request`, `handle_default_request`). This makes the codebase difficult to:

1. **Test**: Load balancing and routing logic cannot be unit tested in isolation
2. **Extend**: Adding new load balancing algorithms (e.g., weighted, least-connections) requires modifying core functions
3. **Maintain**: Understanding the routing pipeline requires navigating across multiple files
4. **Scale**: No built-in health checks or circuit breakers for failover
5. **Configure**: Load balancing strategy is hardcoded, not configurable

This change extracts routing logic into a dedicated `routing/` module with support for algorithm transforming, dynamic converter choice, load balancing, and failover.

## What Changes

**New Module Structure:**
```
routing/
├── __init__.py                    # Public API exports + Router facade
├── load_balancer.py              # Load balancing strategies (round-robin, least-connections, weighted)
├── request_router.py               # Request routing logic (endpoint selection, converter choice)
├── protocols/                     # Protocol handlers for different API protocols
│   ├── __init__.py
│   ├── claude_converse.py       # Claude /converse protocol
│   ├── claude_invoke.py          # Claude /invoke protocol
│   ├── gemini_generate.py        # Gemini /generateContent protocol
│   └── openai_chat.py          # OpenAI /chat/completions protocol
├── health.py                     # Health checks and circuit breaker
└── strategy.py                    # Abstract base classes for routing strategies
```

**Key Changes:**
- Extract `load_balance_url()` logic into `routing/load_balancer.py` with strategy pattern
- Extract routing decision tree from handler functions into `routing/request_router.py`
- Create protocol handlers in `routing/protocols/` for each API protocol (Converse, Invoke, GenerateContent)
- Implement health check mechanism for endpoint availability detection
- Add circuit breaker pattern for automatic failover
- Support dynamic load balancing algorithm selection (round-robin, least-connections, weighted)
- Thread-safe load balancing with proper locking
- Backward compatibility facade in `routing/__init__.py`

**Affected Capabilities:**
- `load-balancing` (new) - Load balancing strategies and failover
- `request-routing` (new) - Endpoint selection and protocol handling
- `dynamic-converter-selection` (new) - Dynamic converter choice based on model detection
- `failover` (new) - Health checks and circuit breaker

**Affected Code:**
- `proxy_server.py`: Remove `load_balance_url()` and handler routing logic (~200 lines)
- `proxy_helpers.py`: Keep Detector and Converters (unchanged)

## Impact

**Breaking Changes:**
- None - backward compatibility maintained through facade

**Affected Specs:**
- New capability: `load-balancing` - Load balancing strategies and failover mechanisms
- New capability: `request-routing` - Endpoint selection and protocol handling
- New capability: `dynamic-converter-selection` - Dynamic converter choice
- New capability: `failover` - Health checks and circuit breaker

**Test Impact:**
- New unit tests for `routing/` module (~8 test files)
- Integration tests for routing with all providers (Claude, Gemini, OpenAI)
- Estimated >90% coverage on `routing/` module

**Effort:**
- Estimated 8 days (10 implementation phases)

**Success Criteria:**
- `proxy_server.py` reduced by ~200 lines
- Load balancer counters are thread-safe
- New routing module has >90% test coverage
- Health checks and circuit breaker work correctly
- Failover to alternative endpoints when primary is unavailable
- Dynamic load balancing algorithm selection works
- All existing tests pass
