# Troubleshooting Guide

This guide covers common operational and connection issues when running the SAP AI Core LLM Proxy, along with diagnosis steps and solutions.

---

## 1. TLS Certificate Verification Errors

### Symptoms
- `ConnectionError: TLS certificate verification failed`
- `OSError: [SSL: CERTIFICATE_VERIFY_FAILED]` or `CA certificate problem`
- `AIAPIAuthenticatorException` during startup token fetching
- Requests fail with 500 errors

### Root Cause
Occurs when the CA certificate bundle is missing or inaccessible (frequently in `uv` virtual environments or corporate proxies).

### Solution

#### Option A: Auto-Discovery (Default)
The proxy automatically searches for CA certificates in this order:
1. `certifi` Python package
2. Standard system certificate paths
3. Python SSL default context

Verify `certifi` is installed and accessible:
```bash
python -c "import certifi; print(certifi.where())"
```

#### Option B: Configure Explicit CA Bundle
If behind a custom proxy/firewall, specify `ca_cert_bundle` in `config.json`:
```json
{
  "ca_cert_bundle": "/path/to/ca-certificates.crt",
  "subAccounts": { ... }
}
```

**Common certificate paths:**
- **macOS (Homebrew)**: `/opt/homebrew/etc/openssl/cert.pem` or `/usr/local/etc/openssl/cert.pem`
- **Linux (Ubuntu/Debian)**: `/etc/ssl/certs/ca-certificates.crt`
- **Linux (RHEL/CentOS)**: `/etc/ssl/certs/ca-bundle.crt`

#### Automated Recovery Behavior
The proxy implements automatic recovery:
- **Token Fetching**: Retries with system default verification if custom cert fails.
- **Bedrock SDK**: Invalidates the SDK session on certificate error to force fresh initialization with updated configuration.

---

## 2. Authentication & Token Errors

### Symptoms
- `401 Unauthorized` or `403 Forbidden` returned to clients
- `Invalid Bearer token provided` in server logs

### Diagnosis & Fix
1. **Client Authorization Header**:
   Ensure client requests supply a valid token matching `secret_authentication_tokens` from `config.json`:
   ```bash
   curl -H "Authorization: Bearer your-proxy-auth-token" http://127.0.0.1:3001/v1/models
   ```
2. **SAP AI Core Service Key**:
   Verify the subaccount `service_key.json` credentials are valid and have active permissions for the SAP AI Core resource group.

---

## 3. Client Payload & Format Incompatibilities

### Symptoms
- `400 Bad Request` from upstream Claude or SAP AI Core endpoints
- Upstream error: `messages: Unexpected role "system"` or `Extra inputs are not permitted`

### Root Cause & Resolution
- **Nested `system` roles**: The proxy automatically extracts `system` messages anywhere in the `messages` array and converts them to top-level `system` prompt strings.
- **Unsupported fields**: Certain clients (e.g. Claude Code, Kilo Code) send fields like `metadata`, `output_config`, `context_management`. The proxy automatically strips these unsupported fields before forwarding to AWS Bedrock.

---

## 4. Upstream Rate Limiting (HTTP 429)

### Symptoms
- `429 Too Many Requests` or `ThrottlingException: Too many tokens`

### Resolution
- The proxy automatically applies exponential backoff retry (up to 4 attempts) using `tenacity` on Bedrock calls.
- To balance load across accounts, configure multiple subaccounts in `config.json` for round-robin distribution.
