# Tasks

- [x] Remove `ai-api-client-sdk` and `ai-core-sdk` from `pyproject.toml` <!-- id: 0 -->
- [x] Run `uv lock` to update dependencies <!-- id: 1 -->
- [x] Verify application startup to ensure no hidden runtime imports <!-- id: 2 -->
- [x] Remove unused dependencies: `aioboto3`, `langchain-core`, `numpy`, `openi`, `protobuf`, `google-genai`, `urllib3`, `uuid`, `pyasn1`, `uuid-utils`, `pytokens`, `grpcio` <!-- id: 3 -->
- [x] Move dev tools to dev group: `basedpyright`, `pyrefly`, `ruff`, `types-requests` <!-- id: 4 -->
- [x] Run `uv lock` again <!-- id: 5 -->
- [x] Verify tests pass <!-- id: 6 -->