# SOLID Refactor Plan (Hybrid, Low-Risk, 1–2 Weeks)

**Summary**
Focus on the remaining SOLID gaps already documented (notably `proxy_helpers.py` converter extraction and lingering legacy wrappers), plus a quick spot-check of the highest-risk modules. No external API changes; keep backward compatibility while isolating responsibilities, removing global coupling, and tightening interface boundaries.

---

## 1) Goals, Success Criteria, and Scope

**Goals**
- Finish converter extraction from `proxy_helpers.py` into dedicated modules.
- Eliminate legacy wrappers in `proxy_server.py` and reduce global state reliance.
- Ensure routing, streaming, and conversion flows are wired through explicit interfaces (DIP/ISP).
- Maintain identical external behavior (low-risk constraint).

**Success Criteria**
- `proxy_helpers.py` becomes a thin compatibility facade (<= ~200 lines).
- `proxy_server.py` no longer exports wrappers that hide `proxy_config`.
- Converters and streaming conversions live in dedicated modules with a registry.
- All existing unit/integration tests pass; add/adjust tests for extracted modules.

**Out of Scope**
- New features (metrics, rate limiting, caching).
- API changes to external request/response formats.

---

## 2) Architecture Changes (No External API Changes)

### 2.1 Create a Converter Package (SRP/OCP)
**New modules**
- `converters/`
- `converters/__init__.py`
- `converters/base.py` (interfaces/protocols for converters)
- `converters/openai_to_claude.py`
- `converters/openai_to_claude37.py`
- `converters/claude_to_openai.py`
- `converters/claude37_to_openai.py`
- `converters/openai_to_gemini.py`
- `converters/gemini_to_openai.py`
- `converters/cross_model.py` (e.g., claude->gemini, openai->claude delta conversions)
- `converters/streaming.py` (chunk converters, SSE helpers)

**Implementation detail**
- Move converter functions from `proxy_helpers.py` into these modules.
- Introduce a registry dict keyed by `(source_format, target_format, model_family)` in `converters/__init__.py`.

### 2.2 Extract Detector into Dedicated Module (SRP)
**New module**
- `detectors/model_detector.py` (move `Detector` class, `extract_version`, etc.)

**Compatibility**
- `proxy_helpers.py` re-exports `Detector` for backward compatibility.

### 2.3 Refactor `proxy_helpers.py` into a Facade
- Keep `load_model_aliases` if needed.
- Re-export converter functions or provide thin wrappers that delegate to `converters/`.
- Remove logic from `proxy_helpers.py` that does not need to live there.

### 2.4 Remove Legacy Wrappers in `proxy_server.py` (DIP)
- Replace wrapper functions (`handle_claude_request`, `handle_gemini_request`, `handle_default_request`, `load_balance_url`, `resolve_model_name`) with direct imports from:
  - `handlers/model_handlers.py`
  - `load_balancer.py`
- Ensure `proxy_config` is passed explicitly; no hidden globals.

### 2.5 Ensure Blueprint Initialization Uses Explicit Dependencies
- `register_blueprints` already passes config/context; verify each blueprint uses the injected context (no global access).
- If any blueprint or handler still reaches for module globals, pass explicit args or use factory patterns.

---

## 3) Implementation Steps (Decision-Complete)

1. Converter extraction
- Move functions from `proxy_helpers.py` into `converters/` modules.
- Create `converters/__init__.py` registry:
  - Map formats and model families to converter functions.
  - Provide `get_converter(source, target, model_family)`.

2. Streaming conversion extraction
- Move `convert_*_chunk_*` functions into `converters/streaming.py`.
- Update `handlers/streaming_handler.py` and `handlers/streaming_generators.py` to use registry.

3. Detector extraction
- Move `Detector` into `detectors/model_detector.py`.
- Update imports in `proxy_server.py`, handlers, and tests.
- `proxy_helpers.py` re-exports `Detector` for compatibility.

4. Legacy wrapper removal
- Replace wrapper functions in `proxy_server.py` with direct imports.
- Ensure `proxy_config` is passed explicitly into `load_balance_url` and handler calls.

5. Facade clean-up
- Reduce `proxy_helpers.py` to:
  - Compatibility exports
  - Deprecation notes in docstrings (no behavior changes)

6. Spot-check key modules (Hybrid scope)
- Review `handlers/model_handlers.py`, `handlers/streaming_handler.py`, `load_balancer.py` for:
  - Hard-coded globals
  - Overlapping responsibilities
- Refactor only where needed to align with injected dependencies.

---

## 4) Public API/Interface Changes

**None externally.**
Internal changes only:
- New module namespaces (`converters/`, `detectors/`).
- `proxy_helpers.py` becomes a compatibility layer.

---

## 5) Tests and Validation

**Update/Extend Tests**
- Adjust import paths in tests that use `proxy_helpers.py` converters.
- Add unit tests for `converters` registry (converter selection by model family).
- Add streaming conversion tests for chunk paths now in `converters/streaming.py`.

**Regression Runs**
- `make test`
- `make test-integration` (if environment available)

---

## 6) Risks and Mitigations

**Risk**: Broken imports after moving functions.
**Mitigation**: Keep `proxy_helpers.py` as a compatibility facade until all references migrated.

**Risk**: Streaming regressions.
**Mitigation**: Add focused tests for streaming chunk conversion and SSE parsing.

**Risk**: Hidden global usage in handlers.
**Mitigation**: Explicit dependency injection and a quick spot-check.

---

## 7) Timeline (1–2 Weeks)

**Days 1–3**
- Converter extraction + registry
- Update imports

**Days 4–5**
- Streaming extraction
- Update handlers

**Days 6–7**
- Remove wrappers in `proxy_server.py`
- Quick spot-check of handlers/load_balancer

**Days 8–10**
- Tests + regressions
- Final cleanup of `proxy_helpers.py` facade

---

## Assumptions and Defaults
- Low-risk constraint: no external API changes or behavior changes.
- Hybrid scope: targeted gaps + quick spot-check only.
- Timeline: 1–2 weeks; no large architectural overhauls beyond converter extraction.
