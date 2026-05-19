# PROJECT KNOWLEDGE BASE

**Generated:** 2026-01-19
**Commit:** f358537
**Branch:** main

## OVERVIEW
SAP AI Core LLM Proxy - transforms SAP AI Core APIs into OpenAI/Anthropic-compatible endpoints with multi-model load balancing.

## STRUCTURE
```
./
├── proxy_server.py (2563 lines) - Main Flask app, endpoints, load balancing
├── proxy_helpers.py (1430 lines) - Model detection, format conversion
├── auth/ - Token management, request validation (thread-safe)
├── config/ - Pydantic-based configuration parsing
├── utils/ - Logging, error handlers, SDK pooling
├── tests/ - Unit (tests/unit/) and integration (tests/integration/) tests
└── openspec/ - Spec-driven development workflow (see openspec/AGENTS.md)
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add endpoint | proxy_server.py | Add Flask route, use verify_request_token() |
| Add model provider | proxy_helpers.py | Add detection function + converters |
| Modify format conversion | proxy_helpers.py:Converters | Bidirectional converters for OpenAI/Claude/Gemini |
| Token caching | auth/token_manager.py:TokenManager | 5-min buffer before expiry, thread-safe |
| Load balancing | proxy_server.py:load_balance_url() | Round-robin across subaccounts + deployments |
| Configuration | config/config_parser.py | Multi-subaccount JSON config |
| SDK client caching | utils/sdk_pool.py | Thread-safe lazy initialization |
| Streaming | proxy_server.py:generate_streaming_response() | SSE with on-the-fly format conversion |

## CRITICAL IMPLEMENTATION DETAILS

### Model Detection (proxy_helpers.py:Detector)
- `is_claude_37_or_4()` - Claude 3.7/4/4.5 → uses `/converse` endpoint
- `is_claude_model()` - All Claude models (claude-*, sonnet-*, anthropic--)
- `is_gemini_model()` - Gemini models (gemini-*)

### Endpoint Selection (based on model type)
- **Claude 3.7/4/4.5**: `/converse` or `/converse-stream` → parsed with `convert_claude37_to_openai()`
- **Claude 3.5/older**: `/invoke` or `/invoke-with-response-stream` → parsed with `convert_claude_to_openai()`
- **Gemini**: `/generateContent` → parsed with `convert_gemini_to_openai()`
- **GPT/OpenAI**: `/chat/completions` → standard format

### Token Management
- Cached per subaccount with 5-minute buffer before expiry
- Thread-safe using `threading.Lock()`
- Fetch from SAP AI Core OAuth endpoint per subaccount

### Load Balancing
- Round-robin across subaccounts
- Round-robin across deployment URLs within each subaccount
- Model fallback: tries normalized model names if exact match not found
- Counter per subaccount: `proxy_config.subaccounts[name].counter`

### Retry Logic
- Only retries on rate limit errors (429, "too many tokens")
- Exponential backoff: 4 attempts max, 4s-16s wait
- Uses `tenacity` library with `@bedrock_retry` decorator

## CONVENTIONS

### Python (PEP 8)
- Variables/functions: `snake_case` (e.g., `fetch_token`)
- Classes: `PascalCase` (e.g., `ProxyConfig`, `TokenManager`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_CLAUDE_MODEL`)
- Private members: `_leading_underscore`
- Type hints: Required for all function signatures
- Import order: stdlib → third-party → SAP AI SDK imports

### Data Structures
- Use Pydantic models for configuration (ServiceKey, TokenInfo, SubAccountConfig, ProxyConfig)
- Use @dataclass with field() for other data structures

### Error Handling
- Always use try-except with `logging.error()`
- Handle HTTP 429 with conservative retry logic (tenacity)

### Threading
- Use `threading.Lock` for shared state (tokens, SDK clients)
- See `_sdk_session_lock` pattern in utils/sdk_pool.py

### Flask Routes
- Add `logging.info()` at start of each route handler
- Verify tokens with `verify_request_token()` (auth/request_validator.py)

## ANTI-PATTERNS (THIS PROJECT)

1. **Don't bypass token validation** - All endpoints must call `verify_request_token()`
2. **Don't create new connections per request** - Reuse SDK clients from utils/sdk_pool.py
3. **Don't hardcode model names** - Use detection functions from proxy_helpers.py:Detector
4. **Don't suppress type errors** - Never use `as any` or `@ts-ignore` equivalents
5. **Don't modify global state without locks** - Use `threading.Lock` for shared variables

## COMMANDS

### Setup & Running
```bash
uv sync                                  # Install dependencies (uses uv, not pip)
uvx --from . sap-ai-proxy -c config.json  # Run server (primary method - recommended)
uvx --from . sap-ai-proxy -c config.json -d  # Debug mode
python proxy_server.py -c config.json  # Alternative method (legacy)
```

### Testing
```bash
make test                    # Unit tests only (50+ tests, 28% coverage)
make test-integration         # Integration tests (requires running server)
make test-cov                # With coverage report
uv run pytest tests/test_name.py::test_function  # Single test
```

### Building
```bash
make build                    # Build binary with PyInstaller
make build-tested             # Build + test
make version-bump-patch      # Bump version (0.1.0 → 0.1.1)
```

## NOTES

### Known Technical Debt (High Priority)
1. **Monolithic proxy_server.py** - 2563 lines, needs refactoring (see docs/ARCHITECTURE.md)
2. **Hardcoded model normalization** - `normalize_model_names()` has `if False:` at line 56
3. **Limited logging configuration** - Logging levels are hardcoded

### Global State
- `proxy_config` - Loaded ProxyConfig from config.json
- `_bedrock_clients` - Dict of cached Bedrock SDK clients per deployment ID

### SDK Integration
- Uses SAP AI SDK (`gen_ai_hub.proxy.native.amazon.clients.ClientWrapper`) for Bedrock
- Config loaded from `~/.aicore/config.json`
- SDK clients cached per deployment ID with thread-safe lazy initialization

### Additional Documentation
- **CLAUDE.md** - Detailed Claude Code-specific guidance (372 lines)
- **openspec/AGENTS.md** - Spec-driven development workflow (457 lines)
- **docs/ARCHITECTURE.md** - Comprehensive architecture documentation
- **docs/TESTING.md** - Testing guide

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **sap-ai-core-llm-proxy** (5972 symbols, 8424 relationships, 66 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/sap-ai-core-llm-proxy/context` | Codebase overview, check index freshness |
| `gitnexus://repo/sap-ai-core-llm-proxy/clusters` | All functional areas |
| `gitnexus://repo/sap-ai-core-llm-proxy/processes` | All execution flows |
| `gitnexus://repo/sap-ai-core-llm-proxy/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
