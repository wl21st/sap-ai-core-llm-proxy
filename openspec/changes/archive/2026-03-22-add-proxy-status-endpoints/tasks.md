## 1. Project Setup

- [ ] 1.1 Add necessary imports in proxy_server.py for new endpoints
- [ ] 1.2 Ensure config validation checks required keys at startup

## 2. Endpoint Implementation

- [ ] 2.1 Implement `/health` endpoint returning JSON status
- [ ] 2.2 Implement `/stats` endpoint returning request metrics and uptime
- [ ] 2.3 Implement `/info` endpoint returning proxy configuration details

## 3. Metrics Integration

- [ ] 3.1 Connect existing request counters to `/stats` response
- [ ] 3.2 Add uptime calculation based on server start time

## 4. Testing

- [ ] 4.1 Write unit tests for each new endpoint
- [ ] 4.2 Add integration test for config validation logic

## 5. Documentation

- [ ] 5.1 Update README with descriptions of new endpoints
- [ ] 5.2 Add OpenAPI snippet for auto‑generated docs