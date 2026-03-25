## 1. Configuration & Schema Updates

- [x] 1.1 Add `ca_cert_bundle: Optional[str]` field to ProxyConfig Pydantic model in `config/config_parser.py`
- [x] 1.2 Update config documentation (add example of ca_cert_bundle in config.json)
- [x] 1.3 Add docstring to ProxyConfig explaining the ca_cert_bundle field

## 2. Certificate Bundle Discovery Helper

- [x] 2.1 Create `_resolve_ca_cert_bundle()` helper function in `utils/sdk_pool.py`
- [x] 2.2 Implement fallback chain: config → certifi → system paths → stdlib
- [x] 2.3 Add logging at INFO level showing which certificate path is being used
- [x] 2.4 Add early validation: fail at startup if configured path is invalid

## 3. Token Manager Integration

- [x] 3.1 Update `auth/token_manager.py` to accept `ca_cert_bundle` parameter
- [x] 3.2 Pass resolved certificate bundle to `requests.Session(verify=...)` when fetching tokens
- [x] 3.3 Add error handling to distinguish TLS certificate errors from auth failures
- [x] 3.4 Improve error messages to include troubleshooting guidance

## 4. SDK Client Initialization

- [x] 4.1 Update `utils/sdk_pool.py` to pass certificate bundle to SDK client initialization
- [x] 4.2 Research SAP AI SDK's certificate handling mechanism (environment variables, constructor params)
- [x] 4.3 Implement certificate handling in ClientWrapper initialization
- [x] 4.4 Add fallback if SDK doesn't accept explicit certificate parameter

## 5. Integration & Initialization

- [x] 5.1 Update `proxy_server.py` to call certificate resolution during startup
- [x] 5.2 Pass resolved certificate to TokenManager initialization
- [x] 5.3 Ensure certificate is available before first token fetch
- [x] 5.4 Log certificate resolution details at startup

## 6. Error Handling & Logging

- [x] 6.1 Add specific exception handling for OSError with "CA certificate" keywords
- [x] 6.2 Create ProxyError messages for certificate-related failures
- [x] 6.3 Add logging for certificate resolution attempts (success and fallbacks)
- [x] 6.4 Document error scenarios in code comments

## 7. Testing

- [x] 7.1 Unit test: Certificate discovery returns correct path when certifi available
- [x] 7.2 Unit test: Certificate discovery falls back to system paths when certifi unavailable
- [x] 7.3 Unit test: Configuration with invalid ca_cert_bundle fails at startup
- [x] 7.4 Unit test: ProxyConfig parses ca_cert_bundle field correctly
- [x] 7.5 Unit test: Token fetch passes certificate bundle to requests.Session
- [x] 7.6 Unit test: Certificate retry logic and error fallback behavior
  - Created: `tests/unit/test_auth/test_certificate_handling.py` (22 comprehensive tests)
  - Coverage: resolve_ca_cert_bundle(), TokenManager cert handling, retry logic, fallback behavior
  - Result: All 22 tests passing; 57 total auth tests passing

## 8. Documentation & Troubleshooting

- [x] 8.1 Update README with ca_cert_bundle configuration example
- [x] 8.2 Add troubleshooting section: "TLS certificate errors"
- [x] 8.3 Document how to find certificate bundle path on different OSes
- [x] 8.4 Add example config.json with ca_cert_bundle field
- [x] 8.5 Document the fallback chain order and retry logic in TROUBLESHOOTING.md
  - README.md: Added "TLS Certificate Configuration" section with examples
  - TROUBLESHOOTING.md: Added comprehensive TLS troubleshooting guide

## 9. Verification & Cleanup

- [x] 9.1 Run all existing tests (ensure no regressions) - 191 unit tests passing
- [x] 9.2 Verify proxy configuration accepts ca_cert_bundle field - Backward compatible
- [x] 9.3 Fixed exception handling order (Timeout, HTTPError before OSError)
- [x] 9.4 Verify error messages are helpful and actionable - Comprehensive logging added
