## 1. Configuration & Schema Updates

- [ ] 1.1 Add `ca_cert_bundle: Optional[str]` field to ProxyConfig Pydantic model in `config/config_parser.py`
- [ ] 1.2 Update config documentation (add example of ca_cert_bundle in config.json)
- [ ] 1.3 Add docstring to ProxyConfig explaining the ca_cert_bundle field

## 2. Certificate Bundle Discovery Helper

- [ ] 2.1 Create `_resolve_ca_cert_bundle()` helper function in `utils/sdk_pool.py`
- [ ] 2.2 Implement fallback chain: config → certifi → system paths → stdlib
- [ ] 2.3 Add logging at INFO level showing which certificate path is being used
- [ ] 2.4 Add early validation: fail at startup if configured path is invalid

## 3. Token Manager Integration

- [ ] 3.1 Update `auth/token_manager.py` to accept `ca_cert_bundle` parameter
- [ ] 3.2 Pass resolved certificate bundle to `requests.Session(verify=...)` when fetching tokens
- [ ] 3.3 Add error handling to distinguish TLS certificate errors from auth failures
- [ ] 3.4 Improve error messages to include troubleshooting guidance

## 4. SDK Client Initialization

- [ ] 4.1 Update `utils/sdk_pool.py` to pass certificate bundle to SDK client initialization
- [ ] 4.2 Research SAP AI SDK's certificate handling mechanism (environment variables, constructor params)
- [ ] 4.3 Implement certificate handling in ClientWrapper initialization
- [ ] 4.4 Add fallback if SDK doesn't accept explicit certificate parameter

## 5. Integration & Initialization

- [ ] 5.1 Update `proxy_server.py` to call certificate resolution during startup
- [ ] 5.2 Pass resolved certificate to TokenManager initialization
- [ ] 5.3 Ensure certificate is available before first token fetch
- [ ] 5.4 Log certificate resolution details at startup

## 6. Error Handling & Logging

- [ ] 6.1 Add specific exception handling for OSError with "CA certificate" keywords
- [ ] 6.2 Create ProxyError messages for certificate-related failures
- [ ] 6.3 Add logging for certificate resolution attempts (success and fallbacks)
- [ ] 6.4 Document error scenarios in code comments

## 7. Testing

- [ ] 7.1 Unit test: Certificate discovery returns correct path when certifi available
- [ ] 7.2 Unit test: Certificate discovery falls back to system paths when certifi unavailable
- [ ] 7.3 Unit test: Configuration with invalid ca_cert_bundle fails at startup
- [ ] 7.4 Unit test: ProxyConfig parses ca_cert_bundle field correctly
- [ ] 7.5 Unit test: Token fetch passes certificate bundle to requests.Session
- [ ] 7.6 Integration test: Token fetch succeeds with resolved certificate

## 8. Documentation & Troubleshooting

- [ ] 8.1 Update README with ca_cert_bundle configuration example
- [ ] 8.2 Add troubleshooting section: "TLS certificate errors"
- [ ] 8.3 Document how to find certificate bundle path on different OSes
- [ ] 8.4 Add example config.json with ca_cert_bundle commented out
- [ ] 8.5 Document the fallback chain order in comments

## 9. Verification & Cleanup

- [ ] 9.1 Run all existing tests (ensure no regressions)
- [ ] 9.2 Verify proxy starts cleanly with and without ca_cert_bundle configured
- [ ] 9.3 Test with missing certifi scenario (mock OSError)
- [ ] 9.4 Verify error messages are helpful and actionable
