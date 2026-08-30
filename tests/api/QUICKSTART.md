# Quick Start: Running Direct Bedrock API Tests

## 5-Minute Setup

### Step 1: Check Your SAP AI Core Credentials

```bash
# Verify you have the config file
ls -la ~/.aicore/config.json
```

If the file doesn't exist, you need to:
1. Get your `account_key.json` from SAP AI Core
2. Place it at `~/.aicore/config.json`

```bash
# Example setup (if you have account_key.json)
mkdir -p ~/.aicore
cp /path/to/account_key.json ~/.aicore/config.json
chmod 600 ~/.aicore/config.json  # Secure permissions
```

### Step 2: Verify Your Models Are Configured

```bash
# Check what models are in your config
cat ~/.aicore/config.json | python3 -m json.tool | grep -A 5 "deployment_models"
```

You should see entries like:
```json
"deployment_models": {
  "sonnet-4.6": ["https://api.ai.../deployments/..."],
  "opus-4.7": ["https://api.ai.../deployments/..."],
  "haiku-4.5": ["https://api.ai.../deployments/..."]
}
```

If your models have different names, that's OK - tests will skip unavailable models.

### Step 3: Install Dependencies

```bash
# Install project dependencies (if not already done)
uv sync --group dev
```

## Running the Tests

### Option A: Run All API Tests (All Models)

```bash
# Run all tests - shows which models pass/fail
pytest tests/api/ -v

# With logging to see more details
pytest tests/api/ -v --log-cli-level=INFO
```

**Expected Output:**
```
tests/api/test_bedrock_unsupported_fields.py::TestBedrockUnsupportedFieldsDirectAPI::test_metadata_field_rejected[sonnet-4.6] PASSED
✓ Confirmed: Bedrock rejects metadata for sonnet-4.6 (HTTP 400)

tests/api/test_bedrock_unsupported_fields.py::TestBedrockUnsupportedFieldsDirectAPI::test_metadata_field_rejected[opus-4.7] PASSED
✓ Confirmed: Bedrock rejects metadata for opus-4.7 (HTTP 400)

tests/api/test_bedrock_unsupported_fields.py::TestBedrockUnsupportedFieldsDirectAPI::test_valid_request_succeeds[sonnet-4.6] PASSED
✓ Confirmed: Valid requests work for sonnet-4.6 (HTTP 200)
```

### Option B: Run Tests for Specific Model Only

```bash
# Test only sonnet-4.6
pytest tests/api/test_bedrock_unsupported_fields.py -k "sonnet-4.6" -v

# Test only opus-4.7
pytest tests/api/test_bedrock_unsupported_fields.py -k "opus-4.7" -v

# Test only haiku-4.5
pytest tests/api/test_bedrock_unsupported_fields.py -k "haiku-4.5" -v
```

### Option C: Run Specific Test Case

```bash
# Test only metadata rejection across all models
pytest tests/api/ -k "metadata_field_rejected" -v

# Test only valid requests (control test)
pytest tests/api/ -k "valid_request" -v

# Test only thinking config
pytest tests/api/ -k "thinking_without" -v
```

### Option D: Run with Different Verbosity Levels

```bash
# Minimal output (just pass/fail)
pytest tests/api/ -q

# Medium output (one line per test)
pytest tests/api/ -v

# Full output with all details
pytest tests/api/ -vv

# Show print statements and logs
pytest tests/api/ -v -s --log-cli-level=DEBUG
```

## What Each Test Does

### 1. Metadata Field Test
```bash
pytest tests/api/ -k "metadata_field_rejected" -v
```
- Sends `metadata` field to Bedrock
- **Expected Result**: HTTP 400 (Bedrock rejects it)
- **Proves**: Proxy must strip this field

### 2. Output Config Field Test
```bash
pytest tests/api/ -k "output_config_field_rejected" -v
```
- Sends `output_config` field to Bedrock
- **Expected Result**: HTTP 400 (Bedrock rejects it)
- **Proves**: Proxy must strip this field

### 3. Context Management Field Test
```bash
pytest tests/api/ -k "context_management_field_rejected" -v
```
- Sends `context_management` field to Bedrock
- **Expected Result**: HTTP 400 (Bedrock rejects it)
- **Proves**: Proxy must strip this field

### 4. All Unsupported Fields Test
```bash
pytest tests/api/ -k "all_unsupported_fields" -v
```
- Sends all three unsupported fields together
- **Expected Result**: HTTP 400 (Bedrock rejects it)
- **Proves**: Proxy must strip ALL of them

### 5. Valid Request Test (Control)
```bash
pytest tests/api/ -k "valid_request_succeeds" -v
```
- Sends clean request without unsupported fields
- **Expected Result**: HTTP 200 (Bedrock accepts it)
- **Proves**: Setup works correctly

### 6. Thinking Without Context Management Test
```bash
pytest tests/api/ -k "thinking_without" -v
```
- Sends valid thinking config (no nested context_management)
- **Expected Result**: HTTP 200 (Bedrock accepts it)
- **Proves**: Proxy only strips context_management, not thinking itself

## Interpreting Results

### ✅ All Tests Pass
```
======================== 18 passed in 45.23s ========================
```
Perfect! All models and all test cases passed. Your Bedrock is properly configured.

### ⚠️ Some Tests Skipped
```
tests/api/test_bedrock_unsupported_fields.py::...::test_metadata_field_rejected[haiku-4.5] SKIPPED
(reason: Could not get Bedrock client for haiku-4.5: Model haiku-4.5 not configured)
```
That model isn't configured. You can:
1. Add it to your config's `deployment_models`
2. Or skip it with: `pytest tests/api/ -k "not haiku-4.5" -v`

### ❌ Test Fails
```
AssertionError: Expected Bedrock to reject metadata field with 400, got 200.
```
This means:
1. Bedrock accepted the metadata field (unexpected!)
2. Either: Bedrock changed behavior OR your version is different
3. Check Bedrock API documentation for your region/version

## Troubleshooting

### Problem: "Could not load SAP AI Core config"
```
pytest: error: fixture 'bedrock_client_factory' not found
```

**Solution:**
```bash
# Check config exists and is readable
cat ~/.aicore/config.json
ls -la ~/.aicore/config.json

# Verify it's valid JSON
cat ~/.aicore/config.json | python3 -m json.tool

# If file is missing, create it
mkdir -p ~/.aicore
# Copy your account_key.json here
cp /path/to/account_key.json ~/.aicore/config.json
```

### Problem: "Model X not configured in subaccount"
```
SKIPPED - Could not get Bedrock client for sonnet-4.6: Model sonnet-4.6 not configured
```

**Solution:**
```bash
# Check what models ARE configured
cat ~/.aicore/config.json | python3 -c "
import json, sys
config = json.load(sys.stdin)
for name, subaccount in config.get('subAccounts', {}).items():
    print(f'Subaccount: {name}')
    for model, urls in subaccount.get('deployment_models', {}).items():
        print(f'  - {model}: {urls[0] if urls else \"NO URL\"}')"

# Then run tests for available models only
pytest tests/api/ -k "not haiku-4.5" -v
```

### Problem: Connection timeout or certificate error
```
SSLError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed
```

**Solution:**
```bash
# Run with debug logging to see the issue
pytest tests/api/ -vv --log-cli-level=DEBUG

# If it's a proxy/firewall issue, verify connectivity first
curl -v https://your-sap-ai-core-endpoint/

# If it's a certificate issue, check your config has the right endpoint
cat ~/.aicore/config.json | python3 -c "
import json, sys
config = json.load(sys.stdin)
for subaccount in config.get('subAccounts', {}).values():
    for urls in subaccount.get('deployment_models', {}).values():
        print(urls[0] if urls else 'No URL')"
```

### Problem: "No such file or directory: ~/.aicore/config.json"
```bash
# The ~ might not expand in your shell
# Use full path instead
export HOME="/Users/sfuser"
pytest tests/api/ -v

# Or create it explicitly
mkdir -p ~/.aicore
cp account_key.json ~/.aicore/config.json
```

## Running from Different Locations

```bash
# From project root
pytest tests/api/ -v

# From project root with full path
pytest /Users/sfuser/PycharmProjects/sap-ai-core-llm-proxy/tests/api/ -v

# Change to tests directory first
cd /Users/sfuser/PycharmProjects/sap-ai-core-llm-proxy/tests
pytest api/ -v
```

## Advanced Usage

### Run with Coverage Report
```bash
pytest tests/api/ --cov=tests.api --cov-report=html
# Opens htmlcov/index.html
```

### Run with Verbose Output and Stop on First Failure
```bash
pytest tests/api/ -vv -x
```

### Run in Parallel (for faster execution)
```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests in parallel using 4 workers
pytest tests/api/ -n 4 -v
```

### Generate Test Report
```bash
# Create a detailed HTML report
pytest tests/api/ -v --html=report.html --self-contained-html

# Open the report
open report.html
```

## Understanding Test Output

Each test prints a confirmation line showing what Bedrock did:

```
✓ Confirmed: Bedrock rejects metadata for sonnet-4.6 (HTTP 400)
✓ Confirmed: Bedrock rejects output_config for opus-4.7 (HTTP 400)
✓ Confirmed: Valid requests work for haiku-4.5 (HTTP 200)
✓ Confirmed: Thinking config accepted for sonnet-4.6 (HTTP 200)
```

These prove the negative tests work correctly:
- **400 errors** = Bedrock correctly rejects unsupported fields (good!)
- **200 on valid requests** = Bedrock is working (good!)

## Next Steps

1. ✅ Run: `pytest tests/api/ -v`
2. Verify all 18 tests pass (6 tests × 3 models)
3. Check your proxy server still works: `pytest tests/integration/test_unsupported_fields.py -v`
4. Both should pass, proving:
   - Proxy strips unsupported fields ✓
   - Bedrock rejects unsupported fields ✓
   - Chain is complete ✓

## Getting Help

If tests fail:
1. Check the error message carefully
2. See troubleshooting section above
3. Run with `--log-cli-level=DEBUG` for details
4. Check ~/.aicore/config.json is valid
5. Verify models are configured and accessible
