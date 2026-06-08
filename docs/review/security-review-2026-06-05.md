# Security Review — 2026-06-05

Reviewed by: Claude Code (automated security review)
Branch: main (up to date with origin/main)
Scope: Full codebase review

---

# Vuln 1: Authentication Bypass via Substring Token Comparison: `auth/request_validator.py:55`

* **Severity:** High
* **Category:** `auth_bypass`
* **Confidence:** 8/10

**Description:**
The token validation logic uses a substring containment check (`valid_token in token`) instead of equality. The `_extract_token` method returns the raw `Authorization` header value without stripping the `Bearer ` prefix, so the substring check was introduced to handle both `Bearer <token>` and bare `<token>` forms. However, this means a valid token matches if it appears **anywhere** inside the submitted string — not just as the full token value.

```python
# auth/request_validator.py:55
if not any(valid_token in token for valid_token in self.valid_tokens):
```

**Exploit Scenario:**
An attacker who obtains a valid token `sk-prod-abc123` (via a leak, shared credential, or observation) can authenticate using any string that contains it as a substring — for example:

```
Authorization: Bearer sk-prod-abc123<arbitrary_suffix>
```

Because `"sk-prod-abc123" in "Bearer sk-prod-abc123<arbitrary_suffix>"` evaluates to `True`, the request is accepted. This undermines token rotation: rotating `sk-prod-abc123` does not invalidate derived tokens that were crafted with it embedded.

Additionally, if the configuration ever contains an empty string in `secret_authentication_tokens`, `"" in <any_value>` is always `True`, granting access to every request that supplies any Authorization header at all.

**Recommendation:**
Strip the `Bearer ` prefix explicitly in `_extract_token`, then use constant-time equality comparison:

```python
import hmac

def _extract_token(self, request) -> str:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[len("Bearer "):]
    return header

# In validate():
submitted = self._extract_token(request)
if not any(hmac.compare_digest(valid_token, submitted) for valid_token in self.valid_tokens):
    raise HTTPException(status_code=401, detail="Unauthorized")
```

Using `hmac.compare_digest` also prevents timing-based token oracle attacks.
