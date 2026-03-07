# SOLID Refactor Completion - Jira Ticket Breakdown

**EPIC**: SOLID Refactor Completion  
**Description**: Complete remaining SOLID refactor work by extracting converters and detectors into dedicated modules, removing legacy wrappers, and tightening dependency injection. No external API changes.

---

## Jira Ticket Format

**STORY 1: Create converters package and registry**  
**Description**: Add `converters/` package with module files and a central registry for selecting converters by source/target/model family.  
**Acceptance Criteria**  
- `converters/` package exists with required modules.  
- `converters/__init__.py` exposes a registry and `get_converter(...)`.  
- No behavior changes in existing endpoints.

**STORY 2: Move core converters out of `proxy_helpers.py`**  
**Description**: Extract OpenAI↔Claude and OpenAI↔Gemini converters into dedicated modules and update imports.  
**Acceptance Criteria**  
- Converter functions removed from `proxy_helpers.py` and located in `converters/`.  
- All call sites updated and tests passing.  
- `proxy_helpers.py` provides backward-compatible exports.

**STORY 3: Move cross-model converters**  
**Description**: Extract Claude→Gemini and OpenAI→Claude delta conversions into `converters/cross_model.py`.  
**Acceptance Criteria**  
- Cross-model conversion functions relocated.  
- All call sites updated.  
- No behavior change in responses.

**STORY 4: Move streaming converters**  
**Description**: Extract all `convert_*_chunk_*` functions to `converters/streaming.py` and update streaming handlers to use the registry.  
**Acceptance Criteria**  
- Streaming conversion functions relocated.  
- `handlers/streaming_handler.py` and `handlers/streaming_generators.py` updated.  
- Streaming tests pass.

**STORY 5: Extract model detector**  
**Description**: Move `Detector` and version helpers to `detectors/model_detector.py` and update imports.  
**Acceptance Criteria**  
- `Detector` lives in `detectors/model_detector.py`.  
- All imports updated.  
- `proxy_helpers.py` re-exports `Detector`.

**STORY 6: Remove legacy wrappers in `proxy_server.py`**  
**Description**: Replace wrapper functions with direct imports and explicit `proxy_config` injection.  
**Acceptance Criteria**  
- Wrapper functions removed from `proxy_server.py`.  
- Direct imports used with explicit dependency passing.  
- No behavior change.

**STORY 7: Facade cleanup**  
**Description**: Reduce `proxy_helpers.py` to compatibility exports and thin wrappers only.  
**Acceptance Criteria**  
- `proxy_helpers.py` contains only facade logic.  
- File size reduced significantly (target <= ~200 lines).  
- Backward compatibility preserved.

**STORY 8: Spot-check key modules**  
**Description**: Quick SOLID spot-check of `handlers/model_handlers.py`, `handlers/streaming_handler.py`, `load_balancer.py` for hidden globals and mixed responsibilities.  
**Acceptance Criteria**  
- Any remaining global coupling is removed.  
- No functional changes beyond refactor.

**STORY 9: Tests and regression**  
**Description**: Update tests for new module locations and add registry/streaming tests.  
**Acceptance Criteria**  
- `make test` passes.  
- `make test-integration` passes if environment is available.  
- New tests cover registry selection and streaming conversion.

---

## Markdown Table

| Key | Summary | Type | Priority | Description | Acceptance Criteria |
| --- | --- | --- | --- | --- | --- |
| SOLID-1 | Create converters package and registry | Story | High | Add `converters/` package and registry to select converters by format and model family. | Package exists, registry available, no behavior change. |
| SOLID-2 | Move core converters out of `proxy_helpers.py` | Story | High | Extract OpenAI↔Claude and OpenAI↔Gemini converters into `converters/`. | Functions relocated, imports updated, tests pass, facade exports remain. |
| SOLID-3 | Move cross-model converters | Story | Medium | Extract Claude→Gemini and OpenAI→Claude delta conversions into `converters/cross_model.py`. | Functions relocated, call sites updated, no behavior change. |
| SOLID-4 | Move streaming converters | Story | High | Extract streaming chunk converters and update streaming handlers to use registry. | Functions relocated, handlers updated, streaming tests pass. |
| SOLID-5 | Extract model detector | Story | Medium | Move `Detector` to `detectors/model_detector.py` and update imports. | Imports updated, facade re-exports `Detector`. |
| SOLID-6 | Remove legacy wrappers in `proxy_server.py` | Story | High | Replace wrapper functions with direct imports and explicit dependency injection. | Wrappers removed, explicit config passing, no behavior change. |
| SOLID-7 | Facade cleanup | Story | Medium | Reduce `proxy_helpers.py` to compatibility facade only. | File slimmed, only wrappers/exports remain, compatibility preserved. |
| SOLID-8 | Spot-check key modules | Story | Medium | Review for hidden globals and mixed responsibilities in key modules. | Globals removed where found, minimal refactor. |
| SOLID-9 | Tests and regression | Story | High | Update tests, add registry/streaming tests, run suite. | `make test` passes, integration tests pass if available. |
