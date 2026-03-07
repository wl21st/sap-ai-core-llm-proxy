## Model Manifest and Neutral Adapter Plan

### Current Gaps (codebase)
- Model handling is hardcoded in `proxy_helpers.py` / `proxy_server.py`; branching mixes detection, payload shaping, and streaming parsing.
- Streaming handler assumes OpenAI/Anthropic deltas; Gemini emits different event shapes and reasoning streams are not normalized.
- `max_tokens`/context enforcement differs per provider and is not surfaced to callers.
- Token usage fields diverge across providers; reasoning tokens and cache reads/writes are partially lost when streaming.

### Goals
- Centralize per-model capabilities, limits, and streaming semantics in a declarative manifest.
- Convert a neutral chat contract to provider formats (GPT-5.2, Gemini 3, Claude Sonnet/Opus 4.5) and back.
- Normalize streaming deltas and token usage while enforcing unsupported-feature checks up front.

### Deliverables
1. `config/model_manifest.yaml` describing capabilities, limits, and aliases.
2. Neutral request/response dataclasses plus provider adapters (in `proxy_helpers.py` or `utils/adapters.py`).
3. Stream parser layer that emits a neutral delta format used by `generate_streaming_response()`.
4. Validation hooks for clamping `max_output_tokens`, rejecting unsupported options, and injecting provider-specific headers/params.
5. Tests covering clamping, unsupported-feature errors, stream merging, and usage normalization across providers.

### Manifest Shape (YAML)
- `models`: keyed by stable capability name (e.g., `gpt-5.2`, `gemini-3-pro-preview`, `claude-sonnet-4.5`).
- `aliases`: map friendly names to canonical keys (e.g., `claude-sonnet-latest`).
- Per-model fields: `provider`, `endpoint`, `context_window`, `max_output`, `supports` (stream, function_call, reasoning_control), `token_accounting` (reasoning token visibility), `stream_format`, optional `beta_headers`.
- Reasoning controls are declarative: param name plus allowed values or schema (e.g., `budget_tokens` int).
- Optional `deployments`: overrides keyed by deployment identifier (e.g., Bedrock vs native Anthropic for the same Claude Sonnet model) to express different reasoning support, context limits, endpoints, auth, or stream formats.
- Optional `versions`: list of versioned variants for a capability key with `version`, `released_at`, and diff fields; aliases may point to a specific version or `latest`.

### Deployment-Aware Variability
- Same named model can differ by host: e.g., Claude Sonnet 4.5 on Bedrock may expose different reasoning or beta headers than Anthropic native. Manifest should support per-deployment overrides for `supports`, `context_window`, `max_output`, `stream_format`, and usage visibility.
- Selection flow: neutral `model` + selected deployment (from load balancer) → resolve base model entry then apply deployment override before building payload.
- Keeps load-balancing intact while ensuring capability correctness at the deployment level.

### Capability Reference
| Key | Provider | Context window | Max output | Streaming quirks | Reasoning control | Token usage visibility |
|---|---|---|---|---|---|---|
| gpt-5.2 | OpenAI | 400k | 128k | `choices[].delta` SSE | `reasoning_effort` enum | usage returned; reasoning tokens folded into total |
| gemini-3-pro-preview | Google | 1M | 64k | candidate deltas; partial `content.parts` | `thinking_level` enum; no budget | usage returned; no reasoning split |
| claude-sonnet-4.5 | Anthropic | 200k (beta 1M via header) | 64k | `thinking_delta`, `content_block_delta` events | `thinking` object with optional `budget_tokens` | usage returned; no separate reasoning tokens |
| claude-sonnet-4.5 (bedrock) | AWS Bedrock | host-specific | host-specific | may differ in event shape / reasoning support | verify via Bedrock metadata | usage fields may differ |

### Model Variants and Versioning
- Capture explicit versions (e.g., `claude-sonnet-4.5-2025-10-02`) and expose `latest` alias for compatibility.
- Store per-version diffs: context window, max output, reasoning knobs, streaming event names, safety filters, and usage fields.
- Allow deployment-specific versions (e.g., `claude-sonnet-4.5@bedrock-2025-11-01`) to reflect lagged rollouts on hosted platforms.
- Provide a manifest query helper to select by `model` + optional `version` + `deployment`, falling back to alias resolution.

### Neutral API Contract
- Request: `model`, `messages`, `max_output_tokens`, `stream`, `function_call.mode`, optional `reasoning` block (`level`, optional `budget_tokens`).
- Response: `id`, `model`, `choices[].delta` or `message`, `finish_reason`, `usage` with `{input_tokens, output_tokens, reasoning_tokens?, cache_write_tokens?, cache_read_tokens?, total_tokens}`.

### Streaming Normalization (neutral delta schema)
- Envelope: `{id, model, created, choices:[{index, delta:{role?, content?, function_call?, reasoning?}, finish_reason?}]}`.
- OpenAI: map `choices[].delta` directly; use `finish_reason` when present.
- Anthropic: merge `content_block_delta` into `delta.content`; map `thinking_delta` to `delta.reasoning`; map `message_delta.stop_reason` to `finish_reason`.
- Gemini: each candidate delta → one choice; flatten `content.parts` text into `delta.content` in arrival order.

### Adapter Responsibilities
- Map neutral request → provider payload via manifest; clamp `max_output_tokens` to `max_output` (warn or 400).
- Reasoning control mapping:
  - GPT-5.2: `reasoning.level` → `reasoning_effort`.
  - Gemini 3: `reasoning.level` → `thinking_level`; reject if `budget_tokens` supplied.
  - Claude 4.5: `reasoning` → `thinking` object; surface thinking stream events.
- Function calling: pass through only when `supports.function_call` is true; otherwise return 400 with reason.
- Streaming: set provider flags; register parser by `stream_format`.

### Request/Response Conversion Flow
1. Neutral request arrives → manifest lookup (with alias resolution).
2. Validate features against `supports`; clamp context/output limits (after applying deployment and version overrides).
3. Adapter builds provider payload (adds headers such as Claude 1M-context beta when required).
4. Dispatch through existing load balancer.
5. If streaming: provider stream → parser → neutral deltas → `generate_streaming_response()`.
6. On completion: usage reconciler maps provider usage into neutral `usage` and attaches to final chunk.

### Validation and Error Handling
- Unsupported feature → 400 with explicit reason.
- Over-limit tokens → clamp or 400 based on policy flag; record clamp in logs/metrics.
- Beta headers: inject when requested context exceeds default and model exposes `beta_headers`.
- Log fields: `manifest_key`, `alias_used`, `clamped_max_output`, `reasoning_mapped_to`, `stream_format`.
- Deployment overrides: log `deployment_id` and whether overrides were applied.

### Token Usage Normalization
- GPT-5.2: total includes reasoning tokens; set `reasoning_tokens: null`, keep totals.
- Gemini 3: usage present; no reasoning split.
- Claude 4.5: usage present; thinking cost folded into total.
- If provider omits fields during stream, accumulate from final summary chunk.
- Caching: normalize provider-specific cache semantics (prompt caching, response caching) into `cache_write_tokens` / `cache_read_tokens` when exposed; if absent, set to zero/unknown but keep totals consistent.

### Integration Points
- `proxy_helpers.py`: manifest loader (cached), neutral dataclasses, adapters, stream parsers.
- `proxy_server.py`: swap hardcoded model detection for manifest lookup; select parser in `generate_streaming_response()`.
- `config/__init__`: manifest path configurable via CLI flag and env var.

### Testing Matrix (unit level)
- Exceed `max_output_tokens` per provider → clamp behavior asserted.
- Reasoning requested on non-supporting model → 400.
- Claude thinking deltas merge into neutral `delta.reasoning` without losing order.
- GPT-5.2 reasoning tokens hidden but totals preserved.
- Gemini streaming emits ordered partial content without duplication.
- Alias resolution selects canonical model and endpoint.
- Function call request on non-supporting model returns clear error.

### Observability
- Counters: unsupported-feature rejects, clamp occurrences, parser errors per provider.
- Timing: adapter/build latency, stream-to-delta latency.
- Structured logs carry `manifest_key` and `stream_format` for quick triage.

### Rollout Steps
1. Add manifest file and loader.
2. Implement neutral dataclasses and adapters for OpenAI, Gemini, Anthropic.
3. Hook adapters into dispatch and streaming response code.
4. Add tests; run `make test`.
5. Document neutral contract in `docs/neutral-api.md` and link from `README.md`.

### Feasibility Analysis
**Why it’s worth it**
- Single source of truth for limits/semantics, easing model swaps and additions.
- Decouples detection/load-balancing from payload shaping and streaming parsing.
- Enables fast, explicit validation for unsupported features and token clamping.
- Normalized usage/streaming simplifies downstream consumers.

**Costs / risks**
- More moving parts (manifest, adapters, parsers) increase maintenance surface.
- Manifest drift risk if not versioned and owned; needs schema validation + review.
- Streaming edge cases (reasoning deltas, function calls) can regress without fixtures.
- Small added latency from mapping/validation.

**Mitigations**
- Treat manifest as code: versioned, schema-validated in CI, with reviewers.
- Golden streaming fixtures per provider to lock parser behavior.
- Measure overhead; keep adapters pure and zero-copy where possible.
- Ownership: assign a maintainer; document update procedure.

**When to skip**
- If targeting only one provider or a fixed, unchanging model set, abstraction may be overkill.

### External Metadata and Versioning
- Some platforms (SAP AI Core, OpenRouter) expose model catalogs with versions and capability metadata. Add an optional ingestion step that can hydrate or validate manifest entries from these sources.
- Prefer explicit version pins in manifest (e.g., `claude-sonnet-4.5-2025-10-02`) with aliases pointing to “latest” to avoid surprise upgrades.
- Allow hot-reload of manifest with audit logging when refreshed from external catalogs; gate by checksum to avoid partial updates.

### Quick Comparison: Bedrock vs OpenRouter vs Direct APIs
- **AWS Bedrock (Claude/GPT)**: auth via AWS SigV4; model IDs per deployment; event stream frames (`payload`) differ from vendor SSE; reasoning/thinking support can lag native; usage sometimes only in final message; region- and account-level throttling varies by deployment; beta headers may not be exposed.
- **OpenRouter**: aggregator with OpenAI-like surface; routing layer may alter latency and apply safety filters; model names often `vendor/model`; usage fields not guaranteed; some providers’ deltas normalized, others passthrough; caching/reroute can change effective model version.
- **Direct vendor APIs** (OpenAI, Anthropic, Google): canonical feature set and earliest rollout; streaming/usage as documented; payload shapes diverge per vendor.
- Manifest should encode these platform deltas inside `deployments` and/or `versions`, with flags for missing usage, altered stream event names, differing reasoning support, and required auth/headers.

### Cache Bridging Considerations
- Capture cache capabilities per deployment/version: whether prompt caching is supported, cache key shape (prompt hash vs explicit key), TTL, and accounting fields (`cache_write_tokens`, `cache_read_tokens`).
- Adapters should surface a neutral `cache` hint (e.g., `use_cache: true`, `cache_key`, `ttl_seconds`) and map/ignore per provider; fail fast if requested but unsupported.
- Usage reconciliation should preserve cache token accounting when provided (OpenAI and some Bedrock models); if a platform hides cache usage, set fields to null but keep `total_tokens` unchanged.
- Log when cache hints are dropped due to unsupported provider/deployment to avoid silent misconfigurations.
