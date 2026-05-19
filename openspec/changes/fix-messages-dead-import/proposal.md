## Why

`routers/messages.py` imports `generate_claude_streaming_response` but **never calls it**.
The only streaming call in the file is `generate_bedrock_streaming_response` (line 401).

```python
# messages.py lines 18-20
from handlers.streaming_generators import (
    generate_bedrock_streaming_response,
    generate_claude_streaming_response,   # imported, never called
)
```

This is confirmed by a full search across all routers, handlers, and `main.py`:
`generate_claude_streaming_response` has zero live call sites outside of the backward-compat
shim in `proxy_server.py`, which exists only for test imports.

### Why this matters beyond tidiness

`generate_claude_streaming_response` has a known correctness bug: it hardcodes
`input_tokens: 0` in the `message_start` event (tracked in change
`fix-generate-claude-streaming-input-tokens`). The dead import signals to future developers
that this function is the intended streaming helper for the messages router — a reasonable
inference. If someone routes `/v1/messages` streaming through it before the bug is fixed,
clients will silently receive wrong token counts with no error and no indication anything
is wrong.

Removing the import provides an immediate `NameError` if anyone accidentally activates that
path, making the bug fail loudly rather than silently.

## What Changes

Remove the unused import from `routers/messages.py`:

```python
# Before
from handlers.streaming_generators import (
    generate_bedrock_streaming_response,
    generate_claude_streaming_response,
)

# After
from handlers.streaming_generators import (
    generate_bedrock_streaming_response,
)
```

No other files are modified. No functional change at runtime.

## Capabilities

### Modified Capabilities

None. Dead-code removal with no runtime effect.

## Impact

- **Files affected**: `routers/messages.py` (one import line removed)
- **New files**: none
- **Breaking changes**: None. `generate_claude_streaming_response` remains defined in
  `handlers/streaming_generators.py` and re-exported from `proxy_server.py` for tests.
- **Side effects**: None.

## Sequencing

Independent of `fix-generate-claude-streaming-input-tokens`. Can ship in any order — the
import is dead regardless of whether the underlying function is corrected.
