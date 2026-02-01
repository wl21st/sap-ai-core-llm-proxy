# Configuration Validation and Filtering

## Overview

The proxy includes built-in validation to ensure your `config.json` mappings match the actual deployed models in SAP AI Core. This prevents silent misrouting of requests and makes configuration errors immediately visible.

## Automatic Validation

### What Gets Validated

At startup, the proxy validates each configured model mapping:

1. **Family Mismatch** - Detects when model families don't match
   - Example: Configuring `gpt-4` but deployment runs `gemini-pro` → WARNING
   - Families: `gpt`, `claude`, `gemini`, `text-embedding`

2. **Version Mismatch** - Detects version incompatibilities
   - Example: Configuring `gpt-4` but deployment runs `gpt-3.5-turbo` → WARNING
   - Checks: `4-5`, `4`, `3-5`, `3`, `1-5`, `1-0`

3. **Variant Mismatch** - Detects variant incompatibilities
   - Example: Configuring `claude-sonnet` but deployment runs `claude-haiku` → WARNING
   - Variants: `sonnet`, `haiku`, `opus`, `pro`, `flash`, `turbo`, `omni`

### Example Warnings

```
WARNING: Configuration mismatch: Model 'gpt-4' mapped to deployment 'd456' which is running 'gemini-1.5-pro' (Family mismatch)
WARNING: Configuration mismatch: Model 'claude-3-sonnet' mapped to deployment 'd789' which is running 'claude-3-haiku' (Variant mismatch)
WARNING: Configuration mismatch: Model 'gpt-4' mapped to deployment 'd999' which is running 'gpt-3.5-turbo' (Version mismatch)
WARNING: Configuration warning: Deployment 'd000' mapped to model 'gpt-4' not found in subaccount
```

### How It Works

1. During startup, the proxy fetches all available deployments from SAP AI Core
2. For each manual mapping in `config.json`, it compares:
   - Configured model name (what you specified)
   - Backend model name (what's actually deployed)
3. If mismatches are detected, warnings are logged to help you fix the configuration
4. **Important**: Validation is non-blocking - the proxy continues to start even with mismatches

## How to Handle Validation Warnings

### Step 1: Check Server Logs

When starting the proxy, check for validation warnings:

```bash
uvx --from . sap-ai-proxy -c config.json
```

Look for lines containing `Configuration mismatch` or `Configuration warning`.

### Step 2: Inspect Your Deployment

Use the `inspect_deployments.py` utility to see what models are actually deployed:

```bash
python inspect_deployments.py -s demokey.json
```

This shows all available deployments and their actual model names.

### Step 3: Update config.json

Correct your mappings to match the actual deployed models:

**Before (causing mismatch):**
```json
{
  "deployment_models": {
    "gpt-4": ["https://api.../deployments/d456"]  // But d456 runs gemini-pro!
  }
}
```

**After (corrected):**
```json
{
  "deployment_models": {
    "gemini-pro": ["https://api.../deployments/d456"]  // Now matches
  }
}
```

### Step 4: Restart and Verify

Restart the proxy and verify no warnings appear:

```bash
uvx --from . sap-ai-proxy -c config.json 2>&1 | grep "Configuration"
```

No output = no mismatches ✓

## Future: Custom Filter Keywords

**Note**: Custom filter keywords for selective deployment matching are planned for a future release. When implemented, this will allow configuration like:

```json
{
  "subAccounts": {
    "production": {
      "model_filters": {
        "gpt": [".*4.*"],
        "claude": ["sonnet-3-5"],
        "gemini": [".*pro.*"]
      }
    }
  }
}
```

Until then, use the validation warnings to guide your configuration.

## Troubleshooting

### Q: Why is my deployment not appearing?

**A**: Check that:
1. The service key has correct permissions
2. The resource group matches (usually "default")
3. The deployment isn't in a different region/subaccount

Use `inspect_deployments.py` to verify visibility.

### Q: Can I ignore the warnings?

**A**: You can, but you shouldn't. Warnings indicate that your configured model won't properly route to the intended deployment. This could cause:
- Requests sent to wrong model type
- Unexpected API errors
- Silent failures hard to debug

### Q: Does validation block startup?

**A**: No. Warnings are logged but startup continues. This allows you to make corrections and restart without downtime.

## Related Files

- Implementation: `proxy_helpers.py:Detector.validate_model_mapping()`
- Config parsing: `config/config_parser.py:_build_mapping_for_subaccount()`
- Tests: `tests/unit/test_model_validation.py`
- Utilities: `inspect_deployments.py` (for viewing deployments)
