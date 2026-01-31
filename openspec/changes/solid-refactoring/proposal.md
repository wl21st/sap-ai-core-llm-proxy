## Why

The codebase has grown organically with 19 identified SOLID principle violations across 8 key files. The main pain points are: (1) the monolithic `Converters` class with 1350+ lines handling 12+ conversion types, making it hard to test and extend; (2) scattered model detection logic requiring changes in 5+ files to add a new model provider; and (3) tight coupling through global state that makes unit testing difficult (current coverage is only 28%).

## What Changes

- **Extract converters package**: Split the monolithic `Converters` class into focused converter modules organized by model type (OpenAI, Claude, Gemini)
- **Implement Strategy Pattern for model handlers**: Create a model handler registry to eliminate if/elif chains scattered across handlers and blueprints
- **Inject dependencies instead of globals**: Replace module-level `_proxy_config` and `_ctx` globals with Flask's application context
- **Centralize duplicated mappings**: Consolidate stop reason mappings and API version constants currently duplicated in 4+ locations
- **Standardize error responses**: Unify error response formats across blueprints for API consistency

## Capabilities

### New Capabilities
- `converter-architecture`: Defines the new converter package structure with focused single-responsibility modules
- `model-handler-registry`: Defines the strategy pattern for model handling that enables adding new providers without modifying existing code
- `dependency-injection`: Defines how configuration and context flow through the application without global state

### Modified Capabilities
- `model-resolution`: Extend to use the new model handler registry instead of hardcoded detection logic

## Impact

**Code affected:**
- `proxy_helpers.py` - Converters class extracted, Detector class kept but injected
- `handlers/streaming_generators.py` - Refactored to use model handler registry
- `handlers/model_handlers.py` - Replaced with strategy pattern implementation
- `blueprints/*.py` - Updated to use dependency injection via Flask app context
- `load_balancer.py` - ModelResolver extracted as separate concern

**APIs:** No external API changes. Internal interfaces will change.

**Testing:** Expected improvement from 28% to 50%+ coverage due to better testability.

**Risk:** Medium - extensive internal changes but no external API modifications. Requires careful incremental migration.
