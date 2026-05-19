# Journey Into sap-ai-core-llm-proxy

*A technical narrative of the SAP AI Core LLM Proxy project, reconstructed from 217 persistent memory observations spanning March 22 – May 3, 2026.*

---

## 1. Project Genesis

The SAP AI Core LLM Proxy exists to solve a sharp organizational problem: SAP AI Core exposes large language model capabilities through its own proprietary API surface, but the broader developer ecosystem has converged on OpenAI's API format as the de facto standard. Every existing tool, library, and integration speaks the OpenAI dialect. The proxy bridges that gap — transparently translating requests and responses so that any OpenAI-compatible client can speak to Claude, Gemini, or GPT models deployed on SAP's infrastructure without modification.

When the memory record begins on **March 22, 2026 at 12:43 AM**, the project is already well past its inception. The very first observation (#1) reveals not a blank-slate codebase but a mature system with a structured change management discipline: an `openspec/changes` directory containing 11 *archived* completed proposals dating back to January 30, 2026, alongside 9 still-active proposals. Among the archived work: a FastAPI migration, model regex filter support, authentication improvements, and SDK deprecation fixes. The archived proposals tell the story of a project that had already navigated major technical pivots before any of this memory was captured.

The founding technical contract is clear from the architecture: multi-model support (Claude 4.x via AWS Bedrock Converse API, Gemini 2.5 via generateContent, GPT-4o/4.1 via standard endpoints), multi-subaccount load balancing with round-robin distribution, and strict OpenAI API compatibility as the primary client interface. The proxy also implements the Anthropic Messages API natively at `/v1/messages`, making it a bilingual translator in both directions.

---

## 2. Architectural Evolution

The codebase underwent a fundamental restructuring before this memory record begins — and the evidence of that transformation is woven throughout the earliest observations.

**Phase 1: The Flask Era.** The original proxy was a monolithic Flask application, `proxy_server.py`, which at its peak ran to 2,501 lines. Route handlers, format converters, load balancing logic, token management — all lived in a single file. The archived OpenSpec proposals confirm this: "FastAPI migration" appears as a completed change, archived sometime before January 30, 2026.

**Phase 2: FastAPI Migration.** Observation #15 (Mar 22, 12:47 AM) captures the state of this transition with precision. The comment at line 174 of `proxy_server.py` reads: *"All endpoints have been migrated to FastAPI routers (routers/)"*. The `proxy_server.py` entry point is explicitly deprecated at line 180, with the file reduced to backward-compatible wrapper functions — `resolve_model_name`, `load_balance_url`, `parse_sse_response`, and model-specific handlers — that delegate to the new FastAPI application. This architectural pattern, keeping a "facade" file alive for test compatibility while migrating internals, is a deliberate strategy that trades elegance for stability.

The new structure that emerged:
- `routers/` — modular FastAPI routers (chat, embeddings, messages, models, status)
- `handlers/` — model-specific request handlers extracted in Phase 6d (streaming generators)
- `auth/` — authentication and token management
- `config/` — Pydantic-based configuration management
- `utils/` — shared utilities (logging, retry, SDK pool, certificate errors)

Observation #80 (Mar 22, 10:41 AM) confirms the magnitude of this migration: the entire `routers/` package did not exist at the project's base commit. What was once a single file became a directory of six distinct modules.

**Phase 3: Certificate Infrastructure.** By March 25, the architecture absorbed an entirely new subsystem: TLS certificate handling. The `utils/sdk_pool.py` gained new global state (`__current_ca_cert_bundle` alongside the existing `__sdk_session`, `__proxy_client`, `__model_client_map`), `utils/cert_errors.py` was created from scratch, and the `auth/token_manager.py` grew retry logic with automatic certificate fallback. This wasn't architectural ambition — it was driven by a real operational problem in uv virtual environments where the default certifi bundle is inaccessible.

**Phase 4: Ongoing Modularization.** The active proposals captured in observation #49 tell the story of where the architecture was headed: extract the routing module (116 tasks), extract the converters module (167 tasks), and apply SOLID principles (47 tasks, 51% complete at the time). The proxy was actively on a trajectory from "one big file" toward fully modular design.

---

## 3. Key Breakthroughs

**The Status Endpoints Sprint (Mar 22, 12:42–1:03 AM).** The first session captured in memory is remarkable for its velocity. A new developer entered the project, explored the OpenSpec proposal for `/health`, `/stats`, and `/info` endpoints, and within 21 minutes had implemented and committed the complete feature. The sequence: read the proposal (#4) → understand the task breakdown (#5) → discover the FastAPI architecture (#15, #18) → implement `MetricsCollector` (#19) → implement `StatusRouter` (#20) → wire middleware (#25, #27) → debug six consecutive test failures (#32–#45) → pass all tests (#46) → commit (#48). That debugging cascade through schema validation, wrong attribute names, and mock strategy was solved entirely within a single continuous session.

**The TLS Certificate Discovery (Mar 25, 8:45–9:01 AM).** Perhaps the most technically rich breakthrough in the record. The session (#797cb1d7) opened with the observation that the repository branch was ahead of main with four commits. Working backward from that state, the memory captures the full feature in detail: `resolve_ca_cert_bundle()` with its multi-level fallback chain (certifi → system paths → SSL defaults), `TokenManager` retry logic, `is_certificate_error()` utility with 10+ patterns, and SDK session invalidation differentiated by error type. The implementation spans 12 files and adds 1,107 lines, and all 22 new unit tests pass. Most tellingly: the feature was fully implemented *before* the code review that discovered its redundancies.

**The Streaming Default Correction (Apr 11, 11:04 PM – Apr 12, 6:51 AM).** A session arriving three weeks after the TLS work uncovers a subtle but consequential bug: the `/v1/messages` endpoint was defaulting `stream=True` instead of `stream=False`. Observation #670 captures the discovery with precision — `routers/messages.py` line 155 defaulted to True while `routers/chat.py` line 140 already correctly used False. The breakthrough here was methodical: confirm the bug through code inspection, trace the inconsistency to all three affected handler locations, and implement the fix with the conscious decision (observation #683) *not* to introduce a shared helper for a two-file change. By 6:51 AM, PR #27 was merged.

---

## 4. Work Patterns

The memory record reveals three distinct work rhythms.

**Night sessions driving features.** The status endpoints implementation ran from midnight to 1 AM. The streaming default fix began at 11 PM on April 11. The certificate refactoring sessions ran through the early hours of March 26. There is a pattern of sustained late-night focus sessions driving high-complexity feature work through to completion in a single sitting.

**Code review as a second pass.** A recurring pattern emerges: implement something complete, commit it, then return in a subsequent session to review what was actually shipped. The code review session (S12, Mar 22 at 2:20 AM) is the clearest example — observation #90 is a comprehensive review of the status endpoints implementation that reveals 14 distinct issues including missing authentication on `/stats` and `/info`, spec field name violations (snake_case vs. camelCase), and type annotation errors. The implementation *worked* but violated the specification it was supposed to fulfill.

**Refactor immediately after feature.** The March 25 session implements the TLS certificate system. The same day, a code reuse analysis (observation #115) identifies that `TokenManager` was implementing inline certificate detection with only 3 keywords when `utils/cert_errors.py` already provided comprehensive detection with 10+. Within the same session, the redundancy was consolidated. The March 26 session repeated this: the PR was already open, but additional issues were found and fixed before merge — a TOCTOU race condition in SDK session initialization, missing type annotations, and import order violations.

**Structured change management.** Every non-trivial change followed the OpenSpec workflow: proposal → design → specs → tasks → implementation → archive. The `openspec/changes/` directory shows 11 completed proposals at the start of the record, and three more were completed during the recorded period (status endpoints, TLS certificate fix, streaming default fix). This discipline meant that context about *why* decisions were made survived across sessions.

---

## 5. Technical Debt

The project maintained an unusually self-aware relationship with technical debt, explicitly cataloguing it in `docs/ARCHITECTURE.md` and continuously working to reduce it.

**Accumulated debt (visible at session start):**
- `proxy_server.py` at 2,501 lines — acknowledged as the primary architectural liability
- `normalize_model_names()` with `if False:` at line 56 — dead code explicitly left in place
- Global variables (`proxy_config`, `_bedrock_clients`) surviving from the Flask era
- Hardcoded logging levels
- No connection pooling

**Debt created during the recorded period:**
- The status endpoints implementation shipped with missing authentication and spec violations (observation #90) — debt created by insufficient review before commit, paid back in the subsequent code review session
- The TLS certificate handler introduced code duplication across three locations in `messages.py` (120+ lines of repeated recovery logic, per observation #115) — this was debt created intentionally to ship a working feature, then immediately identified and scheduled for refactoring
- A TOCTOU race condition was introduced in `sdk_pool.py`'s double-checked locking optimization (observation #191) — this was subtle enough that it required explicit analysis to detect, and it was present in a PR ostensibly focused on code quality

**Debt paid during the recorded period:**
- Certificate error detection consolidated from 3-keyword inline to comprehensive `is_certificate_error()` utility (#116)
- `_handle_certificate_recovery()` extracted to eliminate 120+ lines of duplication (#138–#140)
- TOCTOU race fixed by moving lock acquisition to cover all checks (#133)
- Import orders corrected per PEP 8 (#205)
- Type annotations added to `sub_account_config` parameter (#204)

---

## 6. Challenges and Debugging Sagas

**The Test Infrastructure Maze (Mar 22, 2–4 AM).** The code review session revealed that while the status endpoints worked functionally, running the test suite with direct pytest invocation produced 11 failures in streaming generator tests and 2 in chat router tests — all due to a missing async plugin. The discovery (observation #76–#78) was initially alarming but ultimately resolved by identifying that `make test` configures the environment correctly while direct `pytest` invocation does not. The lesson: the project's test infrastructure had a hidden dependency on Makefile environment setup.

**The Service Key Initialization Cascade (Mar 22, 12:57–1:01 AM).** During the status endpoints test implementation, six consecutive test failures cascaded in rapid succession. The failures occurred because `TestClient` required a real `proxy_config`, which required loading a service key file, which required specific schema fields (`serviceurls`), which required a `SubAccountConfig` with a `name` argument, which had a wrong attribute name in the `/info` endpoint. Observations #32–#45 document each failure and its fix. The final resolution was to abandon file-based config loading entirely and mock the config directly — a pragmatic choice that made the tests faster and more reliable.

**The TOCTOU Double-Discovery (Mar 25–26, 2026).** The double-checked locking race condition was found twice. First identified in session #797cb1d7 on March 25 (observation #127) and fixed immediately (#133). Then, on March 26, when reviewing PR #25, observation #191 discovered it *again* — this time in a different context, analyzing the refactored `invalidate_bedrock_client` function. The careful review of the PR revealed that the consolidation of if/else logic had maintained functional behavior (the proxy client was invalidated in both branches before and after), but the analysis required working through CPython GIL semantics to confirm. Observation #194 records the explicit decision to accept the remaining trade-off.

**The Streaming Default Silent Failure (April 11–12).** The streaming default bug (stream defaulting to True) was a silent behavioral failure — no errors were raised, no tests caught it. The proxy would accept `stream=false` requests and respond with streaming SSE anyway. The bug was discovered not through a test failure but through code reading: observation #668 identifies the inconsistency by comparing handler files side-by-side. The fix itself was trivial (three one-line changes), but the investigation involved cross-referencing behavior across `routers/messages.py`, `routers/chat.py`, and `handlers/model_handlers.py`, and confirming that the downstream endpoint selection logic was actually correct and only the default value was wrong.

---

## 7. Memory and Continuity

The persistent memory system played a visible structural role in how sessions connected to each other. Several observations speak directly to cross-session continuity:

**Architecture context on re-entry.** When a session arrived on April 12 (three weeks after the March work), observation #661 immediately re-established the project structure from memory. Observation #665 provided the architectural overview (FastAPI, uvicorn, modular handlers) without requiring file reads. This meant the April debugging session could proceed directly to code inspection rather than spending time re-learning the codebase topology.

**OpenSpec workflow continuity.** The OpenSpec proposal workflow inherently spans sessions — proposals are created in one session, implemented in another, reviewed in a third, archived in a fourth. The memory system captured the state of each proposal (observation #49 documents 11 tracked changes with task completion percentages), ensuring that a new session could pick up mid-workflow without losing context.

**Certificate work continuity.** The TLS certificate implementation (March 25) directly informed the refactoring sessions (March 25 afternoon and March 26). Observation #112 opens the refactoring session by summarizing the four commits already made to the TLS branch, establishing what had been done and setting up the next phase of work.

**The stats cited in the timeline header tell the quantitative story**: 212 observations holding 79,283 tokens of compressed knowledge, representing 795,109 tokens of actual work — a 90% compression ratio. Each subsequent session entering a familiar context avoids re-reading code that has already been analyzed and recorded.

---

## 8. Token Economics and Memory ROI

The following figures come from direct SQL queries against `~/.claude-mem/claude-mem.db`.

### Summary Statistics

| Metric | Value |
|--------|-------|
| Total observations | 217 |
| Distinct sessions | 11 |
| Total discovery tokens (generation cost) | 804,175 |
| Total work tokens (context represented) | 795,109 |
| Compressed read tokens (observation text) | 79,283 |
| Memory compression ratio | ~90% savings |

### Average Token Profile per Observation

| Metric | Value |
|--------|-------|
| Average discovery tokens (generation cost) | 3,706 tokens |
| Average read tokens (observation size) | ~370 tokens |
| Compression factor | ~10:1 |

Every observation costs roughly 3,706 tokens to generate and stores approximately 370 tokens of compressed knowledge. Reading back a stored observation costs 10x fewer tokens than regenerating the same understanding from scratch.

### Top 5 Most Expensive Observations to Generate

| ID | Title | Discovery Tokens |
|----|-------|-----------------|
| 121 | Optimized Certificate Error Recovery with Full Session Invalidation | 89,948 |
| 205 | Import Order Corrected Following PEP 8 Convention | 80,403 |
| 191 | Double-Checked Locking Race Condition Identified | 38,357 |
| 698 | Added comprehensive unit tests for stream parameter default behavior | 28,579 |
| 18 | FastAPI Application Entry Point | 23,696 |

Observation #121 is the single most expensive to generate at 89,948 tokens — it captured a nuanced certificate recovery optimization in a complex concurrent context. Once stored, it can be recalled for roughly 900 tokens. Observation #191's 38,357-token generation cost reflects the depth of analysis required to identify a subtle TOCTOU vulnerability through CPython GIL semantics.

### Monthly Breakdown

| Month | Observations | Discovery Tokens | Sessions |
|-------|-------------|-----------------|---------|
| 2026-03 | 161 | 602,195 | 7 |
| 2026-04 | 54 | 183,420 | 2 |
| 2026-05 | 2 | 18,560 | 2 |

March was the highest-activity month by every measure — seven sessions, 161 observations, and 602,195 tokens of discovery work. The April session was intensive but brief: two sessions on a single day (April 12) that together generated 54 observations covering the complete streaming default fix lifecycle.

### Observation Type Breakdown

| Type | Count | Percentage |
|------|-------|-----------|
| discovery | 101 | 46.5% |
| change | 37 | 17.1% |
| bugfix | 29 | 13.4% |
| feature | 23 | 10.6% |
| refactor | 19 | 8.8% |
| decision | 8 | 3.7% |

The dominance of `discovery` observations (46.5%) reflects the exploratory nature of the work — much of each session involved reading existing code to understand what had been built. The `bugfix` and `refactor` categories together (22.2%) reflect a codebase actively improving its own quality. The 8 `decision` observations are disproportionately valuable: they capture the *why* behind choices, not just the *what*.

---

## 9. Timeline Statistics

| Metric | Value |
|--------|-------|
| **Date range** | 2026-03-22 to 2026-05-03 (42 days) |
| **Total observations** | 217 |
| **Total sessions** | 11 |
| **Most active day** | March 22, 2026 (90 observations) |
| **Second most active day** | April 12, 2026 (54 observations) |
| **Files modified (March work)** | 12 files in TLS feature alone |
| **Test count growth** | 417 → 448 → 468 tests |
| **Coverage** | 88% (stable across recorded period) |
| **PRs merged during period** | #24 (TLS certificate fix), #25 (certificate refactoring), #27 (streaming default fix) |

The recorded timeline captures a 42-day window. Actual development began months earlier (archived proposals date to January 2026), but the memory system only captures activity from the first instrumented session. The three-week gap between March 26 and April 11 is visible in the data — no observations were recorded during that period, either because no sessions occurred or because those sessions were not instrumented.

---

## 10. Lessons and Meta-Observations

**The proposal workflow forces clarity before code.** Every feature implemented during the recorded period — status endpoints, TLS certificate handling, streaming default fix — was preceded by a proposal document that defined scope, listed tasks, and made design decisions explicit. This discipline prevented the most common failure mode of AI-assisted development: writing code that works but doesn't fulfill the actual requirement. The streaming default fix design document (observation #683) explicitly decided *not* to add a shared helper for a two-file change — a decision that would have been easy to get wrong in the heat of implementation.

**Code review and implementation should be separate sessions.** The pattern of "implement now, review later" produced better outcomes than it should have. The code review of the status endpoints implementation (observation #90) found 14 issues that the implementation session missed. The code review of PR #25 found the TOCTOU race condition. There is a consistent pattern: a fresh session viewing completed work finds things that the implementation session, moving quickly toward completion, overlooked. The memory system enables this pattern by preserving full context between sessions.

**Thread safety demands explicit analysis.** Two of the most significant bugs found during the recorded period were threading issues: the TOCTOU race condition in `sdk_pool.py` and, more subtly, the confirmation that the refactored `invalidate_bedrock_client` maintained correct behavior. These bugs require reasoning about interleaving execution that isn't visible in a single-threaded reading of the code. The CPython GIL provides some protection but not enough — and the analysis in observation #191 demonstrates exactly where it falls short.

**Operational failures drive architectural additions.** The TLS certificate subsystem wasn't built because it was architecturally desirable — it was built because the proxy failed in real environments where the default certifi bundle was inaccessible (specifically, uv virtual environments). The system's multi-level fallback chain (certifi → system paths → SSL defaults), automatic retry logic, and session invalidation differentiated by error type are all responses to concrete operational failures. This pattern — where a specific real-world problem forces a more general, well-designed solution — appears throughout the codebase.

**The monolith problem is acknowledged but unsolved.** The project maintains explicit awareness of its primary technical debt: `proxy_server.py` at 2,501 lines. Active proposals exist to extract the routing module (116 tasks) and converters module (167 tasks). The SOLID refactoring was 51% complete at the start of the recorded period. But none of these large refactorings completed during the 42-day window. The recorded work focused on observable correctness (fix the streaming default, add TLS support) and local quality (consolidate certificate handling, fix type annotations). The large structural refactoring remains as future work — a planned debt payment deferred in favor of correctness and reliability.

**Type annotations as quality signal.** A recurring theme throughout the code reviews is type annotations. The missing annotation on `sub_account_config` (observation #195) and `proxy_config` (observation #200) were both found in a PR explicitly focused on *code quality* — meaning even quality-focused work can introduce type annotation regressions. The project's use of `basedpyright` for static type checking provides a systematic check, but only catches annotations that are wrong, not annotations that are missing. The pattern suggests that type annotations are treated as aspirational rather than required — valuable enough to fix when found, but not checked at every PR.

---

*This report was generated from claude-mem persistent memory observations for the `sap-ai-core-llm-proxy` project, covering sessions from March 22, 2026 through May 3, 2026. All observation IDs correspond to entries in `~/.claude-mem/claude-mem.db`. Token statistics reflect the actual cost of generating and storing the knowledge that made this analysis possible.*
