# Tasks: remove-dead-claude-streaming-function

- [x] Delete `generate_claude_streaming_response` (async, ~lines 974–1071) from `handlers/streaming_generators.py`
- [x] Delete `generate_claude_streaming_response_sync` (~lines 1342–1360) from `handlers/streaming_generators.py`
- [x] Remove backward-compat shim from `proxy_server.py`: the `generate_claude_streaming_response_sync` import and the `generate_claude_streaming_response` wrapper function (~lines 38–54)
- [x] Delete `TestGenerateClaudeStreamingResponse` test class from `tests/test_proxy_server_extended.py` (~lines 501–557)
- [x] Run `make test` to confirm no regressions
