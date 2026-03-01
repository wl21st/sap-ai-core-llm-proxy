## Context

The proxy currently loads all models defined in `config.json` under each subaccount's `deployment_models` section without any filtering. The configuration is parsed in `config/config_parser.py` and stored in `config/config_models.py` dataclasses (`ProxyConfig` and `SubAccountConfig`).

Model IDs are keys in the `model_to_deployment_urls` dict within each `SubAccountConfig`. The proxy builds a global `model_to_subaccounts` mapping for load balancing across subaccounts. Model resolution happens in `proxy_server.py` using these pre-built mappings.

**Current State:**
- Config parsing happens at startup via `config_parser.py`
- No model filtering capability exists
- All models in config are exposed through `/v1/models` endpoint
- Model resolution uses the complete set of configured models

**Constraints:**
- Must maintain backwards compatibility (filters are optional)
- Filtering must happen during config parsing, not at request time (performance)
- Must work with existing multi-subaccount architecture
- Regex compilation errors should fail fast during startup

## Goals / Non-Goals

**Goals:**
- Add optional model filtering with regex-based include/exclude patterns
- Apply filters during config parsing to prevent filtered models from entering the system
- Provide clear logging about which models are filtered and why
- Maintain backwards compatibility (no filters = current behavior)
- Support per-subaccount or global filter configuration

**Non-Goals:**
- Runtime/dynamic model filtering (filtering is config-time only)
- UI or API for managing filters (config file only)
- Model filtering based on non-ID attributes (deployment URLs, metadata, etc.)
- Filtering logic in model resolution code (should happen at config load)

## Decisions

### Decision 1: Filter Location - Global vs Per-Subaccount

**Options Considered:**
- **Option A**: Global filters only (apply to all subaccounts)
- **Option B**: Per-subaccount filters only
- **Option C**: Both global and per-subaccount filters (merge logic)

**Choice: Option A - Global filters only (initial implementation)**

**Rationale:**
- Simpler implementation and configuration
- Most common use case is consistent filtering across all subaccounts
- Can be extended to per-subaccount filters later without breaking changes
- Reduces config complexity for users

**Trade-off:** Less flexibility for users who want different filters per subaccount, but this can be added in a future enhancement.

### Decision 2: Filter Application Order

**Options Considered:**
- **Option A**: Exclusive first, then inclusive (blocklist takes priority)
- **Option B**: Inclusive first, then exclusive (allowlist takes priority)
- **Option C**: Independent evaluation (include OR exclude)

**Choice: Option A - Exclusive first, then inclusive**

**Rationale:**
- Security-first approach: exclusions take priority
- Matches common firewall/security filter patterns
- Prevents accidental exposure of blocked models

**Algorithm:**
```python
if exclude patterns exist and model matches any:
    filter out (exclude wins)
elif include patterns exist and model does NOT match any:
    filter out (not in allowlist)
else:
    keep model
```

### Decision 3: Config Schema Structure

**Choice:**
```json
{
  "model_filters": {
    "include": ["^gpt-.*", "^claude-.*"],
    "exclude": [".*-test$", "^experimental-.*"]
  },
  "subAccounts": { ... }
}
```

**Rationale:**
- Top-level `model_filters` is clearly global
- Arrays of regex strings are simple and readable
- Empty or missing arrays mean "no filter"
- Easy to extend with additional filter types later

### Decision 4: Regex Validation and Compilation

**Choice:** Compile all regex patterns at config load time and fail fast on invalid patterns

**Rationale:**
- Catch errors early during startup
- Pre-compiled patterns are more efficient (though not critical since this runs once)
- Clear error messages help users fix config issues

**Implementation:** Use Python's `re.compile()` with try/except during config parsing.

### Decision 5: Logging Strategy

**Choice:** Log at INFO level during startup with summary of filtering actions

**Example Output:**
```
INFO: Model filters configured: include=2 patterns, exclude=2 patterns
INFO: Subaccount 'account1': 15 models configured, 12 after filtering (filtered: gpt-4-test, experimental-claude, ...)
INFO: Total models available: 12 across 1 subaccount(s)
```

**Rationale:**
- Visible in normal logs (not hidden in DEBUG)
- Helps users verify filters are working as intended
- Shows which specific models were filtered out

## Risks / Trade-offs

### Risk: Regex Pattern Complexity

**Risk:** Users may write overly complex or incorrect regex patterns that don't behave as expected

**Mitigation:**
- Provide clear documentation with examples
- Fail fast on invalid regex compilation
- Log which models are filtered with pattern match details (in DEBUG mode)
- Start with simple patterns in examples (prefix/suffix matching)

### Risk: Silent Model Filtering

**Risk:** If filters are misconfigured, expected models might be unintentionally filtered out

**Mitigation:**
- INFO-level logging shows exactly which models were filtered
- Log the count of models before/after filtering per subaccount
- If all models in a subaccount are filtered, log a WARNING

### Risk: Backwards Compatibility

**Risk:** Changes to config structure might break existing deployments

**Mitigation:**
- `model_filters` is completely optional
- Absence of `model_filters` section preserves current behavior exactly
- Pydantic validation with Optional fields ensures graceful handling

### Trade-off: Global vs Per-Subaccount Filters

**Trade-off:** Initial implementation only supports global filters

**Implication:** Users who want different filters per subaccount will need to maintain separate config files or wait for enhancement

**Future Path:** Can add `model_filters` inside each `SubAccountConfig` later, with merge strategy (subaccount filters override global)

## Migration Plan

**Deployment Steps:**

1. **Phase 1: Code deployment**
   - Deploy updated config parsing code
   - No config changes needed yet
   - Verify existing configs continue to work

2. **Phase 2: Optional filter adoption**
   - Users can add `model_filters` section to their config.json
   - Start with conservative patterns
   - Monitor startup logs to verify filtering

3. **Rollback Strategy:**
   - Remove `model_filters` section from config.json
   - Restart proxy
   - All models are loaded (original behavior)

**No database migrations or data transformations needed** - this is purely configuration-driven.

## Open Questions

1. **Should we support regex flags (case-insensitive, multiline, etc.)?**
   - Current decision: No flags initially, all patterns are case-sensitive
   - Can add `flags` array later if needed

2. **Should filtered models appear in `/v1/models` with a disabled flag or be completely hidden?**
   - Current decision: Completely hidden (filtered at config load)
   - Simpler implementation, no API changes

3. **Should we validate that at least one model remains after filtering?**
   - Current decision: Yes, emit WARNING if a subaccount has zero models after filtering
   - Don't fail startup (user might want empty subaccount temporarily)
