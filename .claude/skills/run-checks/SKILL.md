---
name: run-checks
description: Run all pre-commit quality checks in sequence — ruff lint, black format, basedpyright type check, and unit tests. Reports all failures before committing.
disable-model-invocation: true
---

Run the following checks in sequence from the project root. Stop and report failures immediately rather than continuing past errors.

```bash
cd /Users/sfuser/develop/work/sap-ai-core-llm-proxy

echo "=== ruff ==="
uv run ruff check .

echo "=== black ==="
uv run black . --check

echo "=== basedpyright ==="
uv run basedpyright

echo "=== unit tests ==="
make test
```

Report each failure with the tool output. If all pass, say "All checks passed — safe to commit."
