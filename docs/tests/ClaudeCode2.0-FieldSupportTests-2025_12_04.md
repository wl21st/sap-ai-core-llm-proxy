# Claude Code 2.0 Field Support Test Cases Documentation

## Purpose
This document provides test cases to validate whether `context_management` and `metadata` fields are supported by AWS Bedrock's Claude API through SAP AI Core.

## Background
The error "context_management: Extra inputs are not permitted" suggests these fields are unsupported, but we need to test various scenarios to confirm:
1. Which fields are actually unsupported
2. Where they can appear (top-level vs nested)
3. Whether they're conditionally supported based on other parameters

---

## Test Case 1: Top-Level `context_management`

**Objective:** Validate if `context_management` is supported at the root level of the request body.

**Request Body:**
```json
{
  "model": "anthropic--claude-4.5-sonnet",
  "messages": [{"role": "user", "content": "Hello"}],
  "max_tokens": 1024,
  "context_management": {
    "type": "auto",
    "max_context_tokens": 100000
  }
}
```

**Expected Behavior:**
- ❌ Should fail with "Extra inputs are not permitted" if unsupported
- ✅ Should succeed if supported

**Test Command:**
```bash
curl -X POST http://127.0.0.1:3001/v1/messages \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: your-token" \
  -d '{
    "model": "anthropic--claude-4.5-sonnet",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 1024,
    "context_management": {
      "type": "auto",
      "max_context_tokens": 100000
    }
  }'
```

**What to Look For:**
- Check server logs for: `"Removing unsupported top-level field 'context_management'"`
- If error occurs, note the exact error message
- If successful, verify response contains valid Claude output

**Result:** [ ] Pass / [ ] Fail

**Notes:**
_Record any observations here_

---

## Test Case 2: Top-Level `metadata`

**Objective:** Validate if `metadata` field is supported at the root level.

**Request Body:**
```json
{
  "model": "anthropic--claude-4.5-sonnet",
  "messages": [{"role": "user", "content": "Hello"}],
  "max_tokens": 1024,
  "metadata": {
    "user_id": "test-user-123"
  }
}
```

**Expected Behavior:**
- ❌ Should fail if unsupported
- ✅ Should succeed if supported

**Test Command:**
```bash
curl -X POST http://127.0.0.1:3001/v1/messages \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: your-token" \
  -d '{
    "model": "anthropic--claude-4.5-sonnet",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 1024,
    "metadata": {
      "user_id": "test-user-123"
    }
  }'
```

**What to Look For:**
- Check server logs for: `"Removing unsupported top-level field 'metadata'"`
- Verify if metadata is passed through or stripped
- Check if response includes any metadata echo

**Result:** [ ] Pass / [ ] Fail

**Notes:**
_Record any observations here_

---

## Test Case 3: `context_management` Inside `thinking`

**Objective:** Validate if `context_management` is supported as a nested field within `thinking` configuration.

**Request Body:**
```json
{
  "model": "anthropic--claude-4.5-sonnet",
  "messages": [{"role": "user", "content": "Solve: 2+2"}],
  "max_tokens": 2048,
  "thinking": {
    "type": "enabled",
    "budget_tokens": 1000,
    "context_management": {
      "type": "auto"
    }
  }
}
```

**Expected Behavior:**
- ❌ Should fail if context_management is not allowed in thinking
- ✅ Should succeed if it's a valid thinking parameter

**Test Command:**
```bash
curl -X POST http://127.0.0.1:3001/v1/messages \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: your-token" \
  -d '{
    "model": "anthropic--claude-4.5-sonnet",
    "messages": [{"role": "user", "content": "Solve: 2+2"}],
    "max_tokens": 2048,
    "thinking": {
      "type": "enabled",
      "budget_tokens": 1000,
      "context_management": {
        "type": "auto"
      }
    }
  }'
```

**What to Look For:**
- Check server logs for: `"Removing 'context_management' from thinking config"`
- Verify thinking still works without context_management
- Check if extended thinking output is generated

**Result:** [ ] Pass / [ ] Fail

**Notes:**
_Record any observations here_

---

## Test Case 4: Valid `thinking` Without `context_management`

**Objective:** Establish baseline - verify that `thinking` works correctly without any unsupported fields.

**Request Body:**
```json
{
  "model": "anthropic--claude-4.5-sonnet",
  "messages": [{"role": "user", "content": "Solve: 2+2"}],
  "max_tokens": 2048,
  "thinking": {
    "type": "enabled",
    "budget_tokens": 1000
  }
}
```

**Expected Behavior:**
- ✅ Should always succeed (baseline test)

**Test Command:**
```bash
curl -X POST http://127.0.0.1:3001/v1/messages \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: your-token" \
  -d '{
    "model": "anthropic--claude-4.5-sonnet",
    "messages": [{"role": "user", "content": "Solve: 2+2"}],
    "max_tokens": 2048,
    "thinking": {
      "type": "enabled",
      "budget_tokens": 1000
    }
  }'
```

**What to Look For:**
- Should complete successfully
- Response should include thinking content
- No errors in logs

**Result:** [ ] Pass / [ ] Fail

**Notes:**
_Record any observations here_

---

## Test Case 5: Both Top-Level and Nested `context_management`

**Objective:** Test behavior when `context_management` appears in multiple locations.

**Request Body:**
```json
{
  "model": "anthropic--claude-4.5-sonnet",
  "messages": [{"role": "user", "content": "Hello"}],
  "max_tokens": 2048,
  "context_management": {
    "type": "auto"
  },
  "thinking": {
    "type": "enabled",
    "budget_tokens": 1000,
    "context_management": {
      "type": "manual"
    }
  }
}
```

**Expected Behavior:**
- ❌ Should fail if either location is unsupported
- ✅ Should succeed if both are supported

**Test Command:**
```bash
curl -X POST http://127.0.0.1:3001/v1/messages \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: your-token" \
  -d '{
    "model": "anthropic--claude-4.5-sonnet",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 2048,
    "context_management": {
      "type": "auto"
    },
    "thinking": {
      "type": "enabled",
      "budget_tokens": 1000,
      "context_management": {
        "type": "manual"
      }
    }
  }'
```

**What to Look For:**
- Check if both instances are removed
- Verify logs show removal from both locations
- Confirm request still succeeds after removal

**Result:** [ ] Pass / [ ] Fail

**Notes:**
_Record any observations here_

---

## Test Case 6: Claude Code 2.0 Beta Request (Real-World)

**Objective:** Simulate an actual Claude Code 2.0 request with beta features.

**Request Body:**
```json
{
  "model": "anthropic--claude-4.5-sonnet",
  "messages": [
    {
      "role": "user",
      "content": "Write a Python function to calculate fibonacci numbers"
    }
  ],
  "max_tokens": 8192,
  "thinking": {
    "type": "enabled",
    "budget_tokens": 5000
  },
  "stream": false
}
```

**Test Command:**
```bash
curl -X POST "http://127.0.0.1:3001/v1/messages?beta=true" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: your-token" \
  -H "anthropic-beta: extended-thinking-2024-12-01" \
  -d '{
    "model": "anthropic--claude-4.5-sonnet",
    "messages": [{"role": "user", "content": "Write a Python function to calculate fibonacci"}],
    "max_tokens": 8192,
    "thinking": {
      "type": "enabled",
      "budget_tokens": 5000
    }
  }'
```

**What to Look For:**
- Should complete successfully
- Check for thinking blocks in response
- Verify no "Extra inputs" errors
- Monitor token usage

**Result:** [ ] Pass / [ ] Fail

**Notes:**
_Record any observations here_

---

## Test Case 7: Verify Current Code Behavior with Logging

**Objective:** Validate that the current fix correctly identifies and removes unsupported fields.

**Test Command:**
```bash
# Run Test Case 1 and monitor logs for these specific lines:
# - "Original request body keys: ..."
# - "Removing unsupported top-level field 'context_management'"
# - "Final request body keys before Bedrock: ..."
# - "Request body for Bedrock (pretty):"
```

**What to Look For:**
1. Original request body should include `context_management`
2. Log should show removal message
3. Final request body should NOT include `context_management`
4. Request should succeed after removal

**Result:** [ ] Pass / [ ] Fail

**Notes:**
_Record the actual log output here_

---

## Test Case 8: Temporarily Disable Fix to Validate Necessity

**Objective:** Confirm that the fix is actually needed by testing without it.

**Steps:**
1. Comment out lines 2063-2077 in [`proxy_server.py`](../proxy_server.py:2063-2077)
2. Restart the proxy server
3. Run Test Case 1 again
4. Observe the error

**Expected Behavior:**
- Should fail with "context_management: Extra inputs are not permitted"
- This confirms the fix is necessary

**Test Command:**
```bash
# After commenting out the fix code:
curl -X POST http://127.0.0.1:3001/v1/messages \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: your-token" \
  -d '{
    "model": "anthropic--claude-4.5-sonnet",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 1024,
    "context_management": {
      "type": "auto"
    }
  }'
```

**What to Look For:**
- Error message: "Extra inputs are not permitted"
- Specific field mentioned in error
- Request fails without the fix

**Result:** [ ] Pass / [ ] Fail

**Notes:**
_Record the error message here_

---

## AWS Bedrock Claude API Supported Fields Reference

Based on AWS Bedrock documentation (anthropic_version: bedrock-2023-05-31):

### ✅ Officially Supported Fields:
- `anthropic_version` (required)
- `messages` (required)
- `max_tokens` (required)
- `temperature` (optional)
- `top_p` (optional)
- `top_k` (optional)
- `stop_sequences` (optional)
- `system` (optional)
- `tools` (optional)

### ❓ Uncertain/Beta Fields:
- `thinking` - Extended thinking feature (may be beta/preview)
- `context_management` - Not documented in standard API
- `metadata` - May be for tracking/logging only

### ❌ Known Unsupported Fields:
- `cache_control` - Prompt caching (different API)
- `input_examples` - Tool examples (not in Bedrock format)

---

## Validation Steps

Follow these steps systematically:

1. **Run Test Case 4 first** (baseline - should always work)
2. **Run Test Cases 1-3** to identify which fields/locations fail
3. **Run Test Case 5** to test multiple field locations
4. **Run Test Case 6** to simulate real Claude Code 2.0 usage
5. **Run Test Case 7** to verify logging and field removal
6. **Run Test Case 8** to confirm fix necessity
7. **Document all results** in the "Result" checkboxes above

---

## Expected Outcomes Matrix

| Test Case | Without Fix | With Fix | Interpretation |
|-----------|-------------|----------|----------------|
| TC1: Top-level context_management | ❌ Fail | ✅ Pass | Fix correctly removes unsupported field |
| TC2: Top-level metadata | ❌ Fail | ✅ Pass | Fix correctly removes unsupported field |
| TC3: Nested context_management | ❌ Fail | ✅ Pass | Fix correctly removes nested field |
| TC4: Valid thinking only | ✅ Pass | ✅ Pass | Baseline - always works |
| TC5: Both locations | ❌ Fail | ✅ Pass | Fix handles multiple locations |
| TC6: Real Claude Code 2.0 | ❌ Fail | ✅ Pass | Fix solves real-world issue |
| TC7: Logging verification | N/A | ✅ Pass | Confirms field removal |
| TC8: Fix disabled | ❌ Fail | N/A | Proves fix is necessary |

---

## Recommendations

### If All Tests Pass With Fix:
✅ The fix is correct and necessary
✅ `context_management` and `metadata` are unsupported by Bedrock
✅ Keep the current implementation

### If Some Tests Pass Without Fix:
⚠️ The fix may be removing valid fields
⚠️ Need to investigate which fields are actually supported
⚠️ May need to refine the fix to be more selective

### If Tests Fail Even With Fix:
❌ The fix is incomplete
❌ There may be other unsupported fields
❌ Need to add more comprehensive field filtering

---

## Test Results Summary

**Date Tested:** _________________

**Tester:** _________________

**Proxy Version:** _________________

| Test Case | Result | Notes |
|-----------|--------|-------|
| TC1 | [ ] Pass / [ ] Fail | |
| TC2 | [ ] Pass / [ ] Fail | |
| TC3 | [ ] Pass / [ ] Fail | |
| TC4 | [ ] Pass / [ ] Fail | |
| TC5 | [ ] Pass / [ ] Fail | |
| TC6 | [ ] Pass / [ ] Fail | |
| TC7 | [ ] Pass / [ ] Fail | |
| TC8 | [ ] Pass / [ ] Fail | |

**Overall Conclusion:**
_Record your findings here_

**Recommended Actions:**
_List any changes needed based on test results_