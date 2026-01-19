# Design: Extract Converters Module

## Context

The SAP AI Core LLM Proxy has undergone significant refactoring to implement SOLID principles. Phases 1-4 successfully extracted authentication, configuration, and utility modules. However, converter logic remains embedded in `proxy_helpers.py` (~1,407 lines), and streaming generators remain in `proxy_server.py` (~800 lines), creating a monolithic structure that violates Single Responsibility Principle.

This change completes Phase 5 of the architectural refactoring by extracting all converter-related functionality into a dedicated `converters/` module.

### Current Problems

1. **Monolithic proxy_helpers.py**: Contains converter logic, model detection, streaming chunk conversion, and token usage tracking in a single file
2. **Streaming logic in proxy_server.py**: ~800 lines of streaming generators embedded in the main application file
3. **Poor testability**: Large, complex functions are difficult to unit test in isolation
4. **Limited extensibility**: Adding new model providers requires modifying large, complex files
5. **Maintainability issues**: Understanding converter logic requires navigating 1,400+ lines in multiple files

### Constraints

- Must maintain backward compatibility with existing imports from `proxy_helpers.py`
- No external dependencies added (use existing Python stdlib and project dependencies)
- Must preserve existing API behavior (OpenAI, Claude, Gemini format conversions)
- Must maintain thread-safety for streaming generators
- All existing tests must continue to pass

## Goals / Non-Goals

### Goals

1. **Modular Architecture**: Separate converter logic into focused, single-purpose modules
2. **Improved Testability**: Each converter module can be unit tested independently
3. **Better Code Organization**: Logical grouping of converters (request, response, streaming)
4. **Backward Compatibility**: Existing imports from `proxy_helpers.py` continue to work
5. **Reduced Complexity**: Each file <200 lines (except generators due to complexity)
6. **Type Safety**: Maintain type hints throughout extracted code
7. **High Test Coverage**: >90% coverage on `converters/` module

### Non-Goals

- Adding new converter capabilities (this is extraction only)
- Changing converter API signatures (maintain existing behavior)
- Performance optimization (focus on modularity and testability)
- Adding new model providers
- Implementing plugin architecture (future work)

## Decisions

### 1. Module Structure: Hierarchical with Subdirectories

**Decision**: Organize converters into subdirectories by purpose (`request/`, `response/`, `streaming/`)

**Rationale**:
- Logical grouping makes code easier to navigate
- Clear separation of concerns (requests vs responses vs streaming)
- Follows Python package conventions
- Enables focused imports (e.g., `from converters.request.openai_to_claude import convert_openai_to_claude`)

**Alternatives Considered**:
- Flat structure: All files in `converters/` directory
  - Pros: Simpler imports
  - Cons: Large number of files (~17) in one directory, no logical grouping
- Separate packages: `converters_request/`, `converters_response/`, etc.
  - Pros: Clear separation
  - Cons: Over-engineered, makes imports complex, circular dependencies

### 2. Backward Compatibility: Facade Pattern

**Decision**: Keep `proxy_helpers.py` as a thin delegation layer with deprecation warnings

**Rationale**:
- Existing code continues to work without changes
- Deprecation warnings guide users to new imports
- Facade can be removed in future major version
- Low risk - minimal code change

**Alternatives Considered**:
- Delete `proxy_helpers.py` immediately:
  - Pros: Clean break
  - Cons: Breaking change, requires updating all imports immediately
- Alias module (import converters as proxy_helpers):
  - Pros: Zero code duplication
  - Cons: Confusing for debugging, unclear migration path

### 3. Unified Public API: Converters Class

**Decision**: Export `Converters` class from `converters/__init__.py` with static method delegates

**Rationale**:
- Maintains existing `Converters.convert_openai_to_claude()` API pattern
- Allows gradual migration (facade → direct imports → Converters class)
- Clear separation between implementation and public API
- Type-safe (all methods have consistent signatures)

**Alternatives Considered**:
- Direct function exports only (no Converters class):
  - Pros: Simpler
  - Cons: Breaks existing `Converters.convert_*` pattern
- Factory pattern with Converter instances:
  - Pros: More flexible for future extensions
  - Cons: Over-engineering for current needs, adds complexity

### 4. Streaming Generators: Separate Module

**Decision**: Extract streaming generators to `converters/streaming/generators.py` as standalone functions

**Rationale**:
- Separates generator logic from chunk conversion logic
- Generators are complex (~800 lines) and deserve their own file
- Clear dependency chain: generators → chunk converters → detectors/mappings
- Easier to test in isolation

**Alternatives Considered**:
- Keep generators in `proxy_server.py`:
  - Pros: No change to main application file
  - Cons: Violates SRP, large file remains
- Inline generators in chunk converters:
  - Pros: Fewer files
  - Cons: Large functions, harder to test, mixing concerns

### 5. Token Usage: Unified TokenExtractor Class

**Decision**: Create `TokenExtractor` class with static methods for each provider format

**Rationale**:
- Unified interface for extracting tokens from different response formats
- Type-safe with `TokenUsage` dataclass
- Easy to extend for new providers
- Clear separation: extraction vs representation

**Alternatives Considered**:
- Dictionary-based extraction:
  - Pros: Simple
  - Cons: No type safety, harder to extend, unclear API
- Mixin pattern in response converters:
  - Pros: No separate module
  - Cons: Mixes concerns, harder to test extraction independently

### 6. Stop Reason Mapping: StopReasonMapper Class

**Decision**: Create `StopReasonMapper` class with bidirectional mappings

**Rationale**:
- Centralized location for stop/finish reason mappings
- Bidirectional support (Claude↔OpenAI, Gemini↔OpenAI)
- Easy to extend for new providers
- Type-safe with static methods

**Alternatives Considered**:
- Inline dictionaries in converter functions:
  - Pros: No separate module
  - Cons: Duplicated code, harder to maintain
- Configuration file (JSON/YAML):
  - Pros: Externalized configuration
  - Cons: Over-engineering, adds runtime complexity

## Dependencies

### Internal Dependencies

```
converters/streaming/generators.py
  ├─→ converters/detector.py
  ├─→ converters/mappings.py
  └─→ converters/token_usage.py

converters/request/*.py
  └─→ converters/mappings.py

converters/response/*.py
  └─→ converters/mappings.py

converters/streaming/*.py
  └─→ converters/mappings.py
```

### External Dependencies (No New Dependencies)

- `logging`: Python stdlib
- `dataclasses`: Python stdlib
- `typing`: Python stdlib
- `json`: Python stdlib (for streaming)
- `random`, `time`: Python stdlib (for streaming jitter)
- `requests`: Existing project dependency

### Import Ordering

To avoid circular dependencies:
1. `converters/mappings.py` - No internal dependencies (constants only)
2. `converters/detector.py` - No internal dependencies
3. `converters/reasoning.py` - No internal dependencies
4. `converters/token_usage.py` - No internal dependencies
5. `converters/request/*.py` - Depend on mappings
6. `converters/response/*.py` - Depend on mappings
7. `converters/streaming/*.py` - Depend on mappings
8. `converters/streaming/generators.py` - Depend on detector, mappings, token_usage
9. `converters/__init__.py` - Re-exports all modules

## Migration Plan

### Phase-by-Phase Extraction

| Phase | Task | Effort | Files Created/Modified |
|-------|------|--------|------------------------|
| **1** | Create `converters/` directory structure & `__init__.py` files | 0.5d | 8 `__init__.py` files |
| **2** | Extract `mappings.py` (stop reasons, API versions) | 0.5d | 1 file |
| **3** | Extract `detector.py` (model detection) | 0.5d | 1 file |
| **4** | Extract `reasoning.py` (thinking/budget handling) | 1d | 1 file |
| **5** | Extract `token_usage.py` (consumption tracking) | 1d | 1 file |
| **6** | Extract `request/` converters | 1.5d | 5 files |
| **7** | Extract `response/` converters | 1d | 4 files |
| **8** | Extract `streaming/` chunk converters | 1d | 3 files |
| **9** | Move streaming generators to `streaming/generators.py` | 1.5d | 1 file |
| **10** | Update `proxy_helpers.py` as backward-compat facade | 0.5d | 1 file modified |
| **11** | Update imports in `proxy_server.py` | 0.5d | 1 file modified |
| **12** | Add/update unit tests | 1.5d | ~10 test files |

**Total Estimated Effort: 10.5 days**

### Rollback Plan

If issues arise during extraction:

1. **Phase-level rollback**: Each phase is independent; revert the specific phase's commits
2. **Full rollback**: `proxy_helpers.py` facade ensures existing imports continue working
3. **Feature flag**: Add `USE_NEW_CONVERTERS=false` env var to fall back to old code (optional)

### Validation Strategy

**After Each Phase:**
- Run existing test suite to ensure no regressions
- Run `lsp_diagnostics` on modified files
- Verify imports resolve correctly

**After Phase 12:**
- All existing tests pass
- New unit tests achieve >90% coverage on `converters/` module
- Integration tests verify proxy_server.py imports work
- `proxy_helpers.py` facade works with deprecation warnings

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

### Risk 2: Streaming Generator State Issues

**Probability**: Medium
**Impact**: High

**Mitigation**:
- Thorough integration testing for streaming scenarios
- Keep request context encapsulated in `RequestContext` dataclass
- Maintain thread-safety with existing logging patterns
- Test with all supported providers (Claude 3.5, 3.7/4, Gemini, OpenAI)

**Trade-off**:
- Increased testing effort vs. confidence in streaming reliability

### Risk 3: Backward Compatibility Breaks

**Probability**: Low
**Impact**: Medium

**Mitigation**:
- Facade layer with direct delegation
- Deprecation warnings to guide migration
- Integration tests verify all existing import patterns
- Keep `Converters` class API identical

**Trade-off**:
- Extra facade code vs. zero breaking changes

### Risk 4: Test Coverage Gaps

**Probability**: Low
**Impact**: Medium

**Mitigation**:
- Phase 12 dedicated to testing (1.5 days)
- Target >90% coverage on `converters/` module
- Test each converter module independently
- Integration tests for streaming generators

**Trade-off**:
- Additional testing effort vs. regression prevention

## Open Questions

1. **Should we add `USE_NEW_CONVERTERS` feature flag?**
   - Decision: Optional, add only if migration issues arise
   - Rationale: Adds complexity; facade should be sufficient

2. **Should we create a converter registry/factory for extensibility?**
   - Decision: No, this is extraction only (out of scope)
   - Rationale: Adds complexity without immediate need

3. **Should we extract model detection to a separate `models/` module?**
   - Decision: No, keep in `converters/detector.py`
   - Rationale: Detector is tightly coupled to converter selection; moving would create circular dependencies

4. **Should we create abstract base classes for converters?**
   - Decision: No, static functions are sufficient
   - Rationale: Abstract classes add complexity without clear benefit for current use case

## Success Criteria

- [ ] All existing tests pass (295+ tests)
- [ ] No import errors in `proxy_server.py`
- [ ] `proxy_helpers.py` facade works for backward compatibility
- [ ] Deprecation warnings issued on `proxy_helpers` import
- [ ] New unit tests achieve >90% coverage on `converters/` module
- [ ] `proxy_server.py` reduced by ~800+ lines
- [ ] `proxy_helpers.py` reduced to <50 lines (facade only)
- [ ] No circular import warnings
- [ ] Streaming generators work for all providers (Claude 3.5, 3.7/4, Gemini, OpenAI)
- [ ] Token usage tracking works correctly for all formats
- [ ] Reasoning token adjustment works for Claude models
