# Configuration Validation and Filtering

The SAP AI Core LLM Proxy performs automated validation at startup to ensure `config.json` model mappings match the actual deployed models in SAP AI Core.

---

## 1. Automated Validation Checks

At startup, the proxy checks each mapped deployment against the backend model metadata:

1. **Family Mismatch**: Detects conflicting model families (e.g. mapping `gpt-4` to a deployment running `gemini-pro`).
2. **Version Mismatch**: Detects version conflicts (e.g. mapping `gpt-4` to `gpt-3.5-turbo`).
3. **Variant Mismatch**: Detects variant conflicts (e.g. mapping `claude-sonnet` to `claude-haiku`).

> [!NOTE]
> Configuration validation is non-blocking. Warnings are emitted in logs (`WARNING: Configuration mismatch...`), but the proxy continues starting.

---

## 2. Inspecting Deployed Models

Use the `inspect_deployments.py` utility to inspect your SAP AI Core tenant's available deployments and backend model names:

```bash
# Using uvx
uvx --from . inspect -s service_key.json

# Using Python
python inspect_deployments.py -s service_key.json
```

---

## 3. Resolving Configuration Warnings

Update your `config.json` to ensure the model key matches the backend model:

```json
{
  "deployment_models": {
    "gemini-2.5-pro": [
      "https://api.ai.prod.eu-central-1.aws.ml.hana.ondemand.com/v2/inference/deployments/d12345"
    ]
  }
}
```
