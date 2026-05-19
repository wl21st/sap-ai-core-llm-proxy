# Anthropic Token Usage Detail Items

For Anthropic, the closest thing to a “master doc” for token‑usage detail items is the **Usage and Cost API documentation**, plus a few integration docs that enumerate all the metric and field names.[^1][^2][^3]

### 1. Official “master” references

These are the primary docs you’d treat as the authoritative spec for usage items:

- **Usage and Cost API (Claude Console / Admin API)** – documents the `/organizations/usage_report/*` endpoints, grouping dimensions, and the fields that describe token usage, cost, model, context window, etc.[^2][^3]
- **Token counting** – explains what counts as input vs output tokens and how the `usage` object in API responses is computed.[^4][^5]
- **Pricing page** – ties the token counts and feature‑usage items (e.g., web search, cache) to actual USD rates and CCUs.[^6][^7]

In practice, if you want a single canonical source, the **Usage and Cost API doc** is the one to bookmark as the “master doc” for field names and semantics, and the pricing + token‑counting docs as supporting references.[^5][^2][^6]

### 2. Metric / field names defined there

Between the Anthropic docs and the Honeycomb integration, you can reconstruct the full list of key token‑usage detail items:[^3][^1][^2]


| Category | Example fields / metrics |
| :-- | :-- |
| Core tokens | `input_tokens`, `output_tokens` (per request and aggregated in reports)[^2][^5] |
| Reasoning | `thinking_tokens` or similar internal reasoning‑token counts where exposed (varies by product/API surface)[^8] |
| Cache | `cache_creation.ephemeral_1h`, `cache_creation.ephemeral_5m`, `cache_read_input_tokens` (reported as metrics like `anthropic.usage.cache_creation.ephemeral_1h` etc.)[^1] |
| Web search | `web_search_requests` / `anthropic.usage.web_search_requests` for number of searches invoked by the model[^1][^6] |
| Grouping dims | `model`, `service_tier`, `workspace_id`, `api_key`, `context_window` buckets like `0-200k`, `200k-1M`, sometimes `inference_geo` and speed tier[^2][^8][^3] |
| Cost | Per‑bucket cost in cents (USD lowest units) based on per‑model, per‑feature token pricing, then optionally converted to CCUs for Claude Platform on AWS[^6][^2] |

The Usage and Cost API docs describe how these show up in JSON responses, including pagination (`has_more`, `next_page`) and how grouping keys like `description` can be parsed into `model` and `inference_geo`.[^2]

### 3. Where integrations mirror this “master doc”

Several third‑party integrations essentially embed the same schema, which helps to infer the de‑facto master list of metrics:

- **Honeycomb Anthropic Usage \& Cost Monitoring** – explicitly lists token metrics like `anthropic.usage.input_tokens`, `anthropic.usage.output_tokens`, cache metrics, and web search metrics with descriptions.[^1]
- **Vantage / Datadog / Finout** – connect to the same Usage and Cost API and describe that they ingest structured cost and usage data broken down by model, workspace, API key, and other groupings.[^8][^9][^3]

These integrations don’t replace the Anthropic docs, but they function as “mirrors” that confirm the metric names and meanings from the Usage and Cost API.[^3][^1]

If you tell me whether you’re instrumenting your own billing pipeline, building a dashboard (Prometheus/Grafana), or wiring Datadog/Honeycomb, I can pull out the exact field list and suggest a schema that tracks 1:1 with Anthropic’s usage “master doc.”
<span style="display:none">[^10][^11][^12][^13][^14][^15]</span>

<div align="center">⁂</div>

[^1]: https://docs.honeycomb.io/integrations/anthropic-usage-monitoring

[^2]: https://platform.claude.com/docs/en/manage-claude/usage-cost-api

[^3]: https://docs.vantage.sh/connecting_anthropic

[^4]: https://mityjohn.com/?p=360

[^5]: https://platform.claude.com/docs/en/build-with-claude/token-counting

[^6]: https://platform.claude.com/docs/en/about-claude/pricing

[^7]: https://intuitionlabs.ai/articles/claude-pricing-plans-api-costs

[^8]: https://www.finout.io/blog/anthropics-enterprise-analytics

[^9]: https://docs.datadoghq.com/integrations/anthropic-usage-and-costs/

[^10]: https://www.reddit.com/r/ClaudeAI/comments/1qv1w51/how_are_you_monitoring_your_anthropic_api_usage/

[^11]: https://www.anthropic.com/learn/build-with-claude?goal=grow-revenue

[^12]: https://support.claude.com/en/articles/9534590-cost-and-usage-reporting-in-the-claude-console

[^13]: https://www.reddit.com/r/ClaudeAI/comments/1o07hqn/claude_explain_the_massive_token_usage/

[^14]: https://www.anthropic.com/transparency

[^15]: https://code.claude.com/docs/en/costs

