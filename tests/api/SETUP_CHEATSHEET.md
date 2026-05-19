# API Tests Setup & Run Cheatsheet

## TL;DR - One Command to Rule Them All

```bash
# 1. Ensure SAP credentials are in place
mkdir -p ~/.aicore && cp account_key.json ~/.aicore/config.json

# 2. Run all Bedrock API tests
pytest tests/api/ -v

# Done! All 18 tests run (6 tests × 3 models: sonnet-4.6, opus-4.7, haiku-4.5)
```

---

## Setup (One Time)

### ✅ Step 1: Place Your Credentials
```bash
# Get your account_key.json from SAP AI Core
mkdir -p ~/.aicore
cp /path/to/account_key.json ~/.aicore/config.json
chmod 600 ~/.aicore/config.json
```

### ✅ Step 2: Verify It Works
```bash
# Check file exists and is valid JSON
cat ~/.aicore/config.json | python3 -m json.tool | head -20
```

### ✅ Step 3: Check Models Are Available
```bash
# List configured models
cat ~/.aicore/config.json | python3 -c "
import json, sys
config = json.load(sys.stdin)
for name, subaccount in config.get('subAccounts', {}).items():
    print(f'Subaccount: {name}')
    for model in subaccount.get('deployment_models', {}).keys():
        print(f'  ✓ {model}')"
```

---

## Running Tests

### 🎯 Run All Tests (Recommended)
```bash
pytest tests/api/ -v
```
**Result**: 18 tests (6 per model)
**Time**: ~30-60 seconds

### 🎯 Run Specific Model
```bash
pytest tests/api/ -k "sonnet-4.6" -v      # Only sonnet
pytest tests/api/ -k "opus-4.7" -v        # Only opus
pytest tests/api/ -k "haiku-4.5" -v       # Only haiku
```

### 🎯 Run Specific Test Type
```bash
pytest tests/api/ -k "metadata" -v              # Only metadata tests
pytest tests/api/ -k "output_config" -v        # Only output_config tests
pytest tests/api/ -k "context_management" -v   # Only context_management tests
pytest tests/api/ -k "valid_request" -v        # Only valid requests (control)
pytest tests/api/ -k "thinking" -v             # Only thinking tests
```

### 🎯 Run with Different Output Levels
```bash
pytest tests/api/ -q              # Minimal (just . P F S)
pytest tests/api/ -v              # Normal (recommended)
pytest tests/api/ -vv             # Verbose
pytest tests/api/ -vv -s          # Very verbose + show prints
```

### 🎯 Run and Stop on First Failure
```bash
pytest tests/api/ -x -v
```

---

## Understanding Results

### ✅ Success (What You Want)
```
tests/api/test_bedrock_unsupported_fields.py::...::test_metadata_field_rejected[sonnet-4.6] PASSED
✓ Confirmed: Bedrock rejects metadata for sonnet-4.6 (HTTP 400)
```
This means: **Bedrock correctly rejected the unsupported field** ✓

### ⚠️ Skipped (Model Not Configured)
```
tests/api/test_bedrock_unsupported_fields.py::...::test_metadata_field_rejected[haiku-4.5] SKIPPED
(reason: Could not get Bedrock client for haiku-4.5)
```
Fix: Add `haiku-4.5` to your config's `deployment_models`

### ❌ Failed (Something Wrong)
```
AssertionError: Expected Bedrock to reject metadata field with 400, got 200.
```
This means: **Bedrock accepted the field (unexpected!)**
- Check Bedrock API version
- Verify config is correct
- Run with `-vv` for more details

---

## Test Overview (What Each Does)

| Test | What It Sends | Expected Result | Proves |
|------|--------------|-----------------|--------|
| **metadata_field_rejected** | `metadata` field | HTTP 400 | Proxy must strip |
| **output_config_field_rejected** | `output_config` field | HTTP 400 | Proxy must strip |
| **context_management_field_rejected** | `context_management` field | HTTP 400 | Proxy must strip |
| **all_unsupported_fields_rejected** | All 3 fields | HTTP 400 | Proxy must strip all |
| **valid_request_succeeds** | Clean request | HTTP 200 | Setup works |
| **thinking_without_context_management_accepted** | Thinking config | HTTP 200 | Thinking is OK |

---

## Quick Troubleshooting

| Problem | Solution |
|---------|----------|
| **No such file or directory: ~/.aicore/config.json** | `mkdir -p ~/.aicore && cp account_key.json ~/.aicore/config.json` |
| **Could not load SAP AI Core config** | Check file exists: `cat ~/.aicore/config.json` |
| **Model X not configured** | Add to config or skip: `pytest tests/api/ -k "not haiku-4.5"` |
| **Connection timeout** | Check network/VPN, verify endpoint in config |
| **SSL certificate error** | Check config endpoint URL, verify TLS setup |
| **All tests pass but slow** | Normal - hitting real Bedrock backend |

---

## Common Recipes

### Run tests and see what's configured
```bash
pytest tests/api/ -v 2>&1 | grep -E "(PASSED|SKIPPED)"
```

### Run only the control test (valid requests)
```bash
pytest tests/api/ -k "valid_request" -v
```

### Run all rejection tests (negative tests)
```bash
pytest tests/api/ -k "rejected" -v
```

### Run with detailed logging
```bash
pytest tests/api/ -vv --log-cli-level=DEBUG
```

### Generate HTML report
```bash
pytest tests/api/ --html=report.html --self-contained-html && open report.html
```

### Run in parallel (faster)
```bash
pip install pytest-xdist
pytest tests/api/ -n 4 -v
```

---

## Expected Full Output (All Pass)

```
$ pytest tests/api/ -v

tests/api/test_bedrock_unsupported_fields.py::TestBedrockUnsupportedFieldsDirectAPI::test_metadata_field_rejected[sonnet-4.6] PASSED
✓ Confirmed: Bedrock rejects metadata for sonnet-4.6 (HTTP 400)

tests/api/test_bedrock_unsupported_fields.py::TestBedrockUnsupportedFieldsDirectAPI::test_output_config_field_rejected[sonnet-4.6] PASSED
✓ Confirmed: Bedrock rejects output_config for sonnet-4.6 (HTTP 400)

tests/api/test_bedrock_unsupported_fields.py::TestBedrockUnsupportedFieldsDirectAPI::test_context_management_field_rejected[sonnet-4.6] PASSED
✓ Confirmed: Bedrock rejects context_management for sonnet-4.6 (HTTP 400)

tests/api/test_bedrock_unsupported_fields.py::TestBedrockUnsupportedFieldsDirectAPI::test_all_unsupported_fields_rejected[sonnet-4.6] PASSED
✓ Confirmed: Bedrock rejects all unsupported fields for sonnet-4.6 (HTTP 400)

tests/api/test_bedrock_unsupported_fields.py::TestBedrockUnsupportedFieldsDirectAPI::test_valid_request_succeeds[sonnet-4.6] PASSED
✓ Confirmed: Valid requests work for sonnet-4.6 (HTTP 200)

tests/api/test_bedrock_unsupported_fields.py::TestBedrockUnsupportedFieldsDirectAPI::test_thinking_without_context_management_accepted[sonnet-4.6] PASSED
✓ Confirmed: Thinking config accepted for sonnet-4.6 (HTTP 200)

[... 12 more tests for opus-4.7 and haiku-4.5 ...]

======================== 18 passed in 47.32s ========================
```

---

## Integration Flow

```
Anthropic Request (with unsupported fields)
        ↓
    Proxy Server (/v1/messages)
        ↓
    Strip unsupported fields ← [Integration tests verify this ✓]
        ↓
    Clean Request to Bedrock
        ↓
    Bedrock accepts ✓ ← [API tests verify unsupported fields would be rejected ✓]
```

Both test suites together prove the complete chain works!

---

## Where to Get Help

- **QUICKSTART.md** - Detailed setup guide
- **README.md** - Full documentation
- **tests/integration/** - Proxy server tests
- **tests/api/** - These Bedrock API tests
