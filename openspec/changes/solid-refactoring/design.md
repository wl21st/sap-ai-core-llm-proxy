## Context

The SAP AI Core LLM Proxy transforms SAP AI Core APIs into OpenAI/Anthropic-compatible endpoints. The codebase has grown to ~4000 lines across core modules with significant technical debt:

- `proxy_helpers.py:Converters` - 1350+ lines, 12+ conversion methods in one class
- `handlers/streaming_generators.py` - 1039 lines with a 540-line function
- Model detection logic duplicated in 5+ files
- Global state (`_proxy_config`, `_ctx`) injected at module level in all blueprints
- 28% test coverage due to tight coupling

Current architecture makes it impossible to:
- Add a new model provider without modifying multiple files
- Unit test handlers in isolation
- Extend conversion logic without understanding the entire Converters class

## Goals / Non-Goals

**Goals:**
- Extract converters into a package with single-responsibility modules
- Implement Strategy Pattern for model handlers to enable OCP compliance
- Replace global state with Flask application context for DIP compliance
- Improve test coverage to 50%+ through better separation of concerns
- Centralize duplicated constants (stop reasons, API versions)

**Non-Goals:**
- Changing external API contracts (OpenAI/Anthropic compatibility)
- Refactoring proxy_server.py beyond the scope of these patterns
- Performance optimization (this is a maintainability refactor)
- Adding new model providers (that comes after this refactor)

## Decisions

### Decision 1: Converter Package Structure

**Choice:** Create `converters/` package with one module per model family

```
converters/
├── __init__.py           # Re-exports for backward compatibility
├── base.py               # Protocol definitions
├── openai.py             # OpenAI format conversions
├── claude.py             # Claude/Bedrock format conversions
├── gemini.py             # Gemini format conversions
├── chunks.py             # Streaming chunk conversions (all models)
└── mappings.py           # Shared constants (stop reasons, API versions)
```

**Rationale:** 
- Each module handles one model family's conversions (SRP)
- `base.py` defines `Converter` Protocol for type safety
- `chunks.py` stays separate because streaming is cross-cutting
- `mappings.py` centralizes duplicated constants

**Alternatives considered:**
- Single file with smaller classes: Still too large, harder to navigate
- One class per conversion direction: Too granular, 20+ files

### Decision 2: Model Handler Registry (Strategy Pattern)

**Choice:** Implement a registry with automatic handler selection

```python
# handlers/registry.py
class ModelHandlerRegistry:
    _handlers: list[tuple[Callable[[str], bool], type[ModelHandler]]] = []
    
    @classmethod
    def register(cls, detector: Callable[[str], bool]):
        def decorator(handler_cls: type[ModelHandler]):
            cls._handlers.append((detector, handler_cls))
            return handler_cls
        return decorator
    
    @classmethod
    def get_handler(cls, model: str) -> ModelHandler:
        for detector, handler_cls in cls._handlers:
            if detector(model):
                return handler_cls()
        return DefaultHandler()

# Usage in handlers/claude_handler.py
@ModelHandlerRegistry.register(Detector.is_claude_model)
class ClaudeHandler(ModelHandler):
    def handle_request(self, request: Request, config: ProxyConfig) -> Response:
        ...
```

**Rationale:**
- Decorator-based registration is Pythonic and explicit
- Adding a new model = add one file with @register decorator (OCP)
- Eliminates if/elif chains in 5+ locations
- Handlers receive dependencies via method parameters (DIP)

**Alternatives considered:**
- Dict-based registry: Less type-safe, no automatic registration
- Abstract factory: Overkill for this use case

### Decision 3: Dependency Injection via Flask App Context

**Choice:** Store configuration in `current_app.config` during app creation

```python
# proxy_server.py
def create_app(config_path: str) -> Flask:
    app = Flask(__name__)
    proxy_config = load_config(config_path)
    ctx = ProxyGlobalContext(proxy_config)
    
    app.config['proxy_config'] = proxy_config
    app.config['proxy_ctx'] = ctx
    
    app.register_blueprint(chat_completions_bp)
    ...
    return app

# blueprints/chat_completions.py
@chat_completions_bp.route("/v1/chat/completions", methods=["POST"])
def proxy_openai_stream():
    config = current_app.config['proxy_config']
    ctx = current_app.config['proxy_ctx']
    ...
```

**Rationale:**
- Flask's built-in pattern, no external DI framework needed
- `current_app` is thread-safe and request-scoped
- Eliminates `init_module()` functions and global state
- Easy to mock in tests via `app.config` override

**Alternatives considered:**
- Dependency injection library (dependency-injector): Heavy dependency for simple needs
- Pass config through request context: Pollutes every function signature
- Keep globals but add setters: Still hidden dependencies

### Decision 4: Backward Compatibility Layer

**Choice:** Keep `proxy_helpers.py` as a facade during migration

```python
# proxy_helpers.py (during migration)
from converters import openai, claude, gemini
from converters.mappings import STOP_REASON_MAP

class Converters:
    """Deprecated: Use converters package directly."""
    
    @staticmethod
    def convert_openai_to_claude(payload):
        return openai.to_claude(payload)
    
    # ... delegate all methods
```

**Rationale:**
- Allows incremental migration without breaking existing code
- Can add deprecation warnings to guide migration
- Remove facade after all callers updated

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Breaking existing functionality during refactor | Write characterization tests first; migrate one converter at a time |
| Import cycles between new modules | Define clear dependency direction: base → specific converters → chunks |
| Performance regression from additional indirection | Minimal - Python function calls are cheap; profile if needed |
| Incomplete migration leaving two patterns | Track migration progress in tasks.md; don't merge until complete |
| Test coverage gaps during transition | Maintain passing tests throughout; add tests before each extraction |

## Migration Plan

**Phase 1: Foundation (Low Risk)**
1. Create `converters/mappings.py` with centralized constants
2. Create `converters/base.py` with Protocol definitions
3. Update imports in existing code to use new constants

**Phase 2: Extract Converters (Medium Risk)**
4. Extract OpenAI converters to `converters/openai.py`
5. Extract Claude converters to `converters/claude.py`
6. Extract Gemini converters to `converters/gemini.py`
7. Extract chunk converters to `converters/chunks.py`
8. Update `proxy_helpers.py` to delegate to new modules

**Phase 3: Model Handler Registry (Medium Risk)**
9. Create `handlers/registry.py` with ModelHandlerRegistry
10. Create individual handler classes with @register decorator
11. Update streaming_generators.py to use registry
12. Update blueprints to use registry

**Phase 4: Dependency Injection (Lower Risk)**
13. Update `create_app()` to store config in app context
14. Update each blueprint to use `current_app.config`
15. Remove `init_module()` functions and global state

**Phase 5: Cleanup**
16. Remove delegation layer from `proxy_helpers.py`
17. Remove deprecated patterns
18. Update documentation

**Rollback:** Each phase is independently deployable. If issues arise, revert the specific phase's commits.

## Open Questions

1. **Should we extract `Detector` class to its own module?** Currently in `proxy_helpers.py`. Could move to `detection/` or keep alongside registry.

2. **How to handle backward compatibility for external importers?** If any external code imports `from proxy_helpers import Converters`, we need deprecation period.

3. **Should chunk converters be separate or part of each model's module?** Current design separates them, but they share similar patterns.
