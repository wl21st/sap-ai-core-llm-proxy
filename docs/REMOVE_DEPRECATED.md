 # Remove Deprecated Docs

## Summary: Deprecated Documentation Files and Source Code

Based on my analysis of the project, here are the deprecated items:

### **DEPRECATED DOCUMENTATION FILES** (7 files)

These are planning/analysis documents from earlier phases that have been superseded:

1. **`docs/PHASE3_IMPROVEMENTS.md`** - Phase 3 test improvement analysis (outdated; Phase 5 is current)
2. **`docs/PHASE3_TEST_ANALYSIS.md`** - Phase 3 test analysis (outdated; Phase 5 is current)
3. **`docs/PHASE3_COMPLETION.md`** - Phase 3 completion notes (historical reference only)
4. **`docs/PHASE4_IMPLEMENTATION_PLAN.md`** - Phase 4 implementation plan (obsolete; Phase 5 active)
5. **`docs/PHASE4_SUMMARY.md`** - Phase 4 summary (historical reference only)
6. **`docs/PHASE4_COMPLETION.md`** - Phase 4 completion notes (historical reference only)
7. **`docs/REFACTORING_PHASE2.md`** - Phase 2 refactoring notes (legacy reference)

Additional docs marked as outdated:
- **`docs/plans/architecture_review_and_improvement_plan.md`** (line 11: explicitly states "outdated and needs significant updates")

Bug/issue documentation (resolved/reference only):
- **`docs/BUG_REPORT_sonnet-4.5-token-usage-regression.md`** - Regression report (now fixed)
- **`docs/FIX_sonnet-4.5-regression.md`** - Fix documentation (completed)
- **`docs/sonnet-4.5-token-usage-issue.md`** - Issue analysis (resolved)

---

### **DEPRECATED SOURCE CODE**

1. **`archive/proxy_server_litellm.py`** (32KB)
   - Old Flask-based proxy using LiteLLM for routing
   - Replaced by modern modular architecture (blueprints + main.py)
   - No longer maintained

2. **`proxy_helpers.py`** (marked for deprecation)
   - Will emit `DeprecationWarning` on import
   - Message: `"proxy_helpers is deprecated. Import from converters module directly."`
   - To be extracted into `converters/` module
   - Scheduled as part of Phase 5 converter extraction

3. **`proxy_server.py`** (marked as legacy but still functional)
   - Alternative/legacy entry point
   - Still works but deprecated in favor of `main.py`
   - Documentation states: "Alternative method (legacy)"
   - Should migrate to: `uvx --from . sap-ai-proxy -c config.json` (recommended)

---

### **CONFIGURATION & CLI DEPRECATIONS**

- **`--config` flag** - Deprecated in favor of `--profile` flag (per `docs/Backlog.md`)
  - Still works with warning: `"--config flag is deprecated, please use --profile instead"`

---

### **SUMMARY TABLE**

| Item                            | Type   | Status     | Notes                                                |
| ------------------------------- | ------ | ---------- | ---------------------------------------------------- |
| archive/proxy_server_litellm.py | Source | Archived   | Replaced by modular architecture                     |
| proxy_helpers.py                | Source | Deprecated | Will emit DeprecationWarning; extract to converters/ |
| proxy_server.py                 | Source | Legacy     | Still works; use main.py instead                     |
| PHASE3/4 docs                   | Docs   | Outdated   | Reference only; Phase 5 is current                   |
| BUG_REPORT_sonnet-4.5           | Docs   | Resolved   | Reference only; issue fixed                          |
| --config flag                   | CLI    | Deprecated | Use --profile instead                                |
