# Bedrock Unsupported Fields Test Record

**Date:** May 18, 2026  
**Status:** ✅ All 18 tests passing  
**Purpose:** Validate which Anthropic API fields are unsupported by AWS Bedrock, confirming proxy must strip them

## Test Suite Overview

**File:** `tests/api/test_bedrock_unsupported_fields.py`  
**Marker:** `@pytest.mark.bedrock`  
**Models Tested:** 3 model families
- `anthropic--claude-4.6-sonnet` (Sonnet)
- `anthropic--claude-4.7-opus` (Opus)
- `anthropic--claude-4.5-haiku` (Haiku)

## Test Cases

### 1. Metadata Field (`test_metadata_field_rejected`)
**Finding:** ✅ **Bedrock accepts/ignores metadata field**
- Expected: HTTP 400 (field rejected)
- Actual: HTTP 200 (field accepted)
- **Implication:** Proxy can optionally strip this field, but Bedrock won't error if present

### 2. Output Config Field (`test_output_config_field_rejected`)
**Finding:** ✅ **Bedrock rejects output_config field**
- Expected: HTTP 400
- Actual: HTTP 400 ✓
- Error: `output_config: Extra inputs are not permitted`
- **Implication:** Proxy MUST strip this field before forwarding to Bedrock

### 3. Context Management Field (`test_context_management_field_rejected`)
**Finding:** ✅ **Bedrock rejects context_management field**
- Expected: HTTP 400
- Actual: HTTP 400 ✓
- Error: `context_management: Extra inputs are not permitted`
- **Implication:** Proxy MUST strip this field before forwarding to Bedrock

### 4. All Unsupported Fields Combined (`test_all_unsupported_fields_rejected`)
**Finding:** ✅ **Multiple unsupported fields rejected**
- Payload includes: metadata, output_config, context_management
- Expected: HTTP 400
- Actual: HTTP 400 ✓
- Error: First field violation reported
- **Implication:** Proxy stripping any ONE unsupported field won't help if others present

### 5. Valid Request (`test_valid_request_succeeds`)
**Finding:** ✅ **Clean requests succeed**
- Payload: messages + max_tokens (no unsupported fields)
- Expected: HTTP 200
- Actual: HTTP 200 ✓
- **Implication:** Baseline control test confirms client/config work correctly

### 6. Thinking Config (`test_thinking_without_context_management_accepted`)
**Finding:** ✅ **Extended thinking supported (with model-specific variations)**

**Sonnet/Haiku:**
- Config: `thinking: {type: "enabled", budget_tokens: 1024}`
- Expected: HTTP 200
- Actual: HTTP 200 ✓
- Constraint: `max_tokens > thinking.budget_tokens` (2048 > 1024)

**Opus:**
- Config: `thinking: {type: "adaptive"}` + `output_config: {effort: "high"}`
- Expected: HTTP 200
- Actual: HTTP 200 ✓
- Note: Opus requires different thinking syntax and output_config

**Implication:** Proxy should support thinking but adapt to model capabilities

## Key Findings

| Field | Status | Action Required |
|-------|--------|-----------------|
| `metadata` | Accepted/Ignored | Optional to strip |
| `output_config` | Rejected (400) | **MUST strip** |
| `context_management` | Rejected (400) | **MUST strip** |
| `thinking` | Accepted | Support and forward |

## Technical Requirements

### Bedrock Converse API Format
- Message content MUST include `type` field: `{type: "text", "text": "..."}`
- ModelId goes in `invoke_model()` parameter, NOT in request body
- Anthropic version in body is accepted (not in modelId parameter)

### Extended Thinking Constraints
- `max_tokens` must be strictly greater than `thinking.budget_tokens`
- Opus uses `thinking.type.adaptive` instead of `thinking.type.enabled`
- Opus requires `output_config.effort` when using adaptive thinking

## Impact on Proxy

### Fields to Strip Before Forwarding
1. `output_config` (always)
2. `context_management` (always)
3. `metadata` (optional, but recommended for cleanliness)

### Fields to Preserve
1. `thinking` (model-specific adaptation needed for Opus)
2. `anthropic_version`
3. `messages` with proper content structure

## Test Execution

```bash
# Run all Bedrock tests
make test-api

# Run specific model test
pytest tests/api/test_bedrock_unsupported_fields.py -k "sonnet"
```

## Related Documentation
- AWS Bedrock Converse API: https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html
- Claude Extended Thinking: https://docs.claude.com/en/docs/build-with-claude/extended-thinking
- SAP AI Core Integration: See `docs/ARCHITECTURE.md`
