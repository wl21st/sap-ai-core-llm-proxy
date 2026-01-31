# Re-authenticate if token in invalid or expired

## Problem

The current proxy implementation fetches an authentication token from SAP AI Core and caches it. While it checks for token expiration based on the `expires_in` field, it does not handle cases where the token is revoked or becomes invalid before its expiry time. In such cases, the backend returns a 401 or 403 error, which is propagated to the client, causing a failed request.

## Solution

Implement a retry mechanism that detects 401 (Unauthorized) or 403 (Forbidden) errors from the backend. When such an error occurs:

1. Invalidate the cached token for the corresponding subaccount.
2. Fetch a fresh token.
3. Retry the request once with the new token.

## Benefits

- Improved reliability: Transient validation issues or token revocations are handled transparently.
- Better user experience: Users see fewer authentication-related errors.
