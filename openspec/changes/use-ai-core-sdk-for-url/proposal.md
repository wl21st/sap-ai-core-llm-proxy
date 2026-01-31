# Proposal: Use SAP AI Core SDK for Deployment URL

## Goal

Simplify the configuration process by allowing users to provide Deployment IDs instead of full Deployment URLs. The system will use the SAP AI Core SDK to dynamically fetch the required Deployment URLs.

## Problem

Currently, users must manually find and copy the full Deployment URL (e.g., `https://api.../deployments/12345`) into the `config.json`. This is error-prone and verbose. The Deployment ID is the stable identifier found in the AI Launchpad.

## Solution

1. **Configuration**: Extend `SubAccountConfig` to accept `model_to_deployment_ids` mapping.
2. **Resolution**: During startup (or lazily), use the SAP AI Core SDK (via `gen_ai_hub` or `ai_core_sdk`) to query the AI Core API using the Deployment ID.
3. **Integration**: Extract the `service_url` (or equivalent) from the SDK response and populate the internal `model_to_deployment_urls` map used by the proxy.

## Key Changes

- `config/config_models.py`: Add `model_to_deployment_ids` field (or dual-use existing field).
- `config/config_parser.py`: Logic to fetch URLs if IDs are provided.
- `utils/sdk_utils.py`: Helper to fetch deployment details via SDK.

## Benefits

- Reduced configuration complexity.
- Validates Deployment ID existence at startup.
- Leverages existing SAP AI Core SDK dependencies.
