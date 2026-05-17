# Cache Control Exploration — 2026-05-16

**Session type:** Explore mode  
**Topic:** Does the Anthropic proxy handle `cache_control` correctly?  
**Motivation:** Missed cache hits are a significant cost penalty — cache reads cost 10% of base input price vs 100% for uncached tokens.

---

## Context

The proxy transforms SAP AI Core APIs into OpenAI/Anthropic-compatible endpoints.  
Claude Code automatically sends `cache_control: {type: "ephemeral"}` on every request by default.  
If the proxy strips those fields, every Claude Code session pays full input token prices.

Reference docs used:
- `docs/reference/claude_caching_reference.md` — full Anthropic prompt caching spec
- `docs/reference/claude_caching_guide.md` — REST payload shape and practical rules
- [Bedrock prompt caching docs](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html)

---

## Architecture Discovered

The proxy has two completely separate request paths:

```
Client Request
      │
      ├─── /v1/messages  ──────────────────────────────────────────────►  Bedrock SDK
      │    (Anthropic format)          cache_control PRESERVED ✅         (invoke_model)
      │
      └─── /v1/chat/completions  ──── convert_openai_to_claude37() ──►  SAP AI Core HTTP
           (OpenAI format)             cache_control STRIPPED ❌          (/converse endpoint)
```

### SAP AI SDK is a boto3 wrapper (pass-through)

`ClientWrapper` in `gen_ai_hub.proxy.native.amazon.clients` only overrides:
- `_convert_to_request_dict()` — rewrites the URL to SAP AI Core endpoint, adds SAP auth headers
- The JSON body is sent **verbatim** as Bedrock's `invoke_model` API format

This means `cache_control` fields in the body **are forwarded to Bedrock unchanged**.

Bedrock's `invoke_model` API supports `cache_control: {"type": "ephemeral"}` for Claude models — identical format to the Anthropic API.

---

## Findings

### Path 1: `/v1/messages` — Cache Works ✅

**Code path:** `routers/messages.py:208-261`

The body is copied and only these fields are mutated:
- `model` removed (put into URL routing)
- `stream` removed (handled separately)  
- `anthropic_version` set to `bedrock-2023-05-31`
- Explicit `unsupported_fields` removed: `context_management`, `metadata`, `output_config`

**`cache_control` is NOT in the unsupported list — it survives.**

Response fields `cache_creation_input_tokens` and `cache_read_input_tokens` are returned in **snake_case** (same as Anthropic API, confirmed from SSE sample in `tests/integration/test_validators.py:12`).

### Path 2: `/v1/chat/completions` — Cache Silently Stripped ❌

**Code path:** `handlers/model_handlers.py:68` → `Converters.convert_openai_to_claude37()` (`proxy_helpers.py:418-564`)

Two helper functions strip `cache_control`:

| Function | File:Line | What it strips |
|---|---|---|
| `_sanitize_content_block()` | `proxy_helpers.py:306-337` | All non-`type`/`text` fields including `cache_control` |
| `_extract_text_from_content()` | `proxy_helpers.py:340-367` | Collapses content arrays to plain text — all metadata lost |

This stripping is **intentional** — SAP AI Core's `/converse` HTTP endpoint does not accept `cache_control`. A warning is logged but the field is removed silently from the client's perspective.

### Dead Code Note

`Converters.convert_claude_request_for_bedrock()` at `proxy_helpers.py:694` explicitly strips `cache_control` but is **never called in production** — only in tests. It appears to be preparation for a path that was never wired up.

---

## Q&A Summary

### Q1: Does Claude Code send `cache_control` by default?

**Yes.** Claude Code automatically adds `cache_control: {type: "ephemeral"}` to system prompts on every request for supported models. No configuration required — it is the default behaviour.

### Q2: Is Bedrock a pass-through? SAP AI SDK or direct HTTP?

**SAP AI SDK (boto3 wrapper) — effectively a pass-through for the request body.** The SDK rewrites the URL to SAP AI Core and adds auth headers, but the JSON body is sent verbatim. Bedrock's `invoke_model` **does** support `cache_control` for Claude models.

### Q3: Response field naming — camelCase or snake_case?

**snake_case.** Bedrock returns `cache_creation_input_tokens` and `cache_read_input_tokens` (snake_case), same as the Anthropic API. Confirmed from the existing SSE sample in `test_validators.py:12`.

### Q4: Integration tests

Created `tests/integration/test_cache_control.py` with 16 tests across 3 classes.

---

## Cost Impact

| Scenario | Token cost multiplier |
|---|---|
| Cache write (first request) | 1.25× base input price |
| Cache read (subsequent requests) | 0.10× base input price |
| No caching (stripped) | 1.00× base input price every request |

For a Claude Code session with a 10,000-token system prompt (common for agentic tasks):
- With caching: first request 1.25×, all subsequent 0.10× = ~90% savings per turn
- Without caching (stripped): 1.00× every turn = no savings

---

## Summary Table

| Location | Path | `cache_control` on system | `cache_control` on content blocks | Response cache tokens |
|---|---|---|---|---|
| `routers/messages.py:208-261` | `/v1/messages` → Bedrock SDK | ✅ PRESERVED | ✅ PRESERVED | ✅ PRESERVED (verbatim response) |
| `Converters.convert_openai_to_claude37():418-564` | `/v1/chat/completions` → `/converse` | ❌ STRIPPED | ❌ STRIPPED | Partially mapped into `prompt_tokens_details` only |
| `Converters.convert_openai_to_claude():370-416` | `/v1/chat/completions` → `/invoke` | ❌ STRIPPED | ❌ STRIPPED | ❌ LOST entirely |
| `Converters.convert_claude_request_for_bedrock():694-766` | Dead code (tests only) | Passed through | ❌ STRIPPED | N/A |

---

## Deliverable

Integration test file: `tests/integration/test_cache_control.py`

```
TestCacheControlMessagesEndpoint (10 tests — /v1/messages, should PASS)
  test_cache_write_on_first_request            → cache_creation_input_tokens > 0
  test_cache_hit_on_repeated_request           → cache_read_input_tokens > 0 on 2nd call
  test_cache_control_on_message_content_block  → cache_control on message body blocks
  test_usage_fields_present_without_cache_control → baseline without cache
  test_streaming_cache_write_includes_usage_fields → cache fields in SSE message_start

TestCacheControlChatCompletionsEndpoint (4 tests — /v1/chat/completions, stripping documented)
  test_cache_control_stripped_gracefully       → no error when cache_control present
  test_no_cache_tokens_in_chat_completions_response → confirms no cache in OpenAI path

TestCacheControlTokenCostVerification (2 tests)
  test_cost_reduction_across_repeated_requests → 3 sequential calls verify progressive cache
```

Run:
```bash
uv run pytest tests/integration/test_cache_control.py -v --log-cli-level=INFO
```
