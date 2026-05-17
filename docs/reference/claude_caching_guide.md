# how the anthropic cache works what is the rest api payload look like

Anthropic prompt caching works by letting you mark a reusable prefix of the request as cacheable, so later requests with the exact same prefix can reuse the cached computation instead of reprocessing it. The cache covers the prompt in order: `tools` → `system` → `messages`, and it is keyed by an exact match up to the cache breakpoint.[^1_1]

## How it behaves

On the first request, Claude processes the full prefix and writes it to cache; on later requests, it reads that prefix from cache and only processes the new tokens after the last cache breakpoint. The default cache lifetime is 5 minutes, each cache hit refreshes it at no additional cost, and there is also a 1-hour TTL option at higher write cost. Anthropic’s docs also note that prompt caching is ZDR-eligible and that cached KV representations are held in memory, not stored at rest.[^1_1]

## REST payload shape

At a high level, the Messages API request looks like this JSON, with `cache_control` either at the top level for automatic caching or on specific content blocks for explicit breakpoints.[^1_1]

```json
{
  "model": "claude-opus-4-7",
  "max_tokens": 1024,
  "cache_control": { "type": "ephemeral" },
  "system": [
    {
      "type": "text",
      "text": "You are a helpful assistant.",
      "cache_control": { "type": "ephemeral" }
    }
  ],
  "messages": [
    {
      "role": "user",
      "content": "Hello"
    }
  ]
}
```


## Typical API request

In the SDK example from Anthropic’s docs, the cache control is attached to the request so the system can choose the last cacheable block automatically. For a raw REST call, the same payload goes to the Messages endpoint with JSON body and your auth headers; the important part for caching is that the static prefix is identical across calls and the breakpoint is placed on the reusable portion.[^1_1]

## Usage fields to watch

The response includes cache-specific usage metrics: `cache_creation_input_tokens` for tokens written to cache, `cache_read_input_tokens` for tokens read from cache, and `input_tokens` for the uncached tail after the last breakpoint. Total input tokens are the sum of those three fields, which is the easiest way to confirm whether caching is actually happening.[^1_1]

## Practical rule

Put `cache_control` at the end of the part of the prompt that stays the same across requests, not on the changing user message or timestamp-like content. For multi-turn chats, automatic caching is usually the simplest option; for stable system prompts, long docs, or tool schemas, explicit breakpoints give you finer control.[^1_1]
<span style="display:none">[^1_10][^1_11][^1_12][^1_13][^1_14][^1_15][^1_2][^1_3][^1_4][^1_5][^1_6][^1_7][^1_8][^1_9]</span>

<div align="center">⁂</div>

[^1_1]: https://platform.claude.com/docs/en/build-with-claude/prompt-caching

[^1_2]: https://www.mindstudio.ai/blog/anthropic-prompt-caching-claude-subscription-limits/

[^1_3]: https://mager.co/blog/2026-04-29-claude-prompt-caching/

[^1_4]: https://www.reddit.com/r/ClaudeCode/comments/1r9vbjo/someone_at_anthropic_shared_his_tips_on_caching/

[^1_5]: https://dev.to/thegdsks/prompt-caching-with-the-claude-api-a-practical-guide-14ce

[^1_6]: https://www.digitalocean.com/blog/prompt-caching-with-digital-ocean

[^1_7]: https://www.krakend.io/docs/enterprise/ai-gateway/anthropic/

[^1_8]: https://www.youtube.com/watch?v=3cv7YRoJ8_4

[^1_9]: https://www.claudecodecamp.com/p/how-prompt-caching-actually-works-in-claude-code

[^1_10]: https://www.reconify.com/docs/anthropic/restapi

[^1_11]: https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages.html

[^1_12]: https://www.firecrawl.dev/blog/using-prompt-caching-with-anthropic

[^1_13]: https://docs.nexla.com/user-guides/connectors/anthropic_api/anthropic_api_data_source

[^1_14]: https://www.ai.moda/en/blog/anthropics-batches-with-caching

[^1_15]: https://www.youtube.com/watch?v=_0uiiJfsBPI


---

# give some references from anthropic

Here are a few direct Anthropic references on prompt caching and the Messages API:

- Prompt caching docs: [Claude API Docs — Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching).[^2_1]
- Messages API reference: [Claude API Docs — Messages](https://platform.claude.com/docs/en/api/messages).[^2_1]
- Cookbook example: [Anthropic Cookbook — prompt_caching.ipynb](https://github.com/anthropics/anthropic-cookbook/blob/main/misc/prompt_caching.ipynb).[^2_2]

From Anthropic’s docs, the main mechanism is `cache_control: { "type": "ephemeral" }`, and Anthropic shows both automatic caching and explicit breakpoints in request payloads. The docs also describe cache usage fields like `cache_creation_input_tokens` and `cache_read_input_tokens` in the response.[^2_1]

If you want, I can turn those references into a minimal `curl` example or a Python SDK example.
<span style="display:none">[^2_10][^2_11][^2_12][^2_13][^2_14][^2_15][^2_3][^2_4][^2_5][^2_6][^2_7][^2_8][^2_9]</span>

<div align="center">⁂</div>

[^2_1]: https://platform.claude.com/docs/en/build-with-claude/prompt-caching

[^2_2]: https://github.com/anthropics/anthropic-cookbook/blob/main/misc/prompt_caching.ipynb

[^2_3]: https://www.mindstudio.ai/blog/anthropic-prompt-caching-claude-subscription-limits/

[^2_4]: https://platform.minimax.io/docs/api-reference/anthropic-api-compatible-cache

[^2_5]: https://developers.llamaindex.ai/python/framework/integrations/llm/anthropic_prompt_caching/

[^2_6]: https://spring.io/blog/2025/10/27/spring-ai-anthropic-prompt-caching-blog

[^2_7]: https://github.com/montevive/autocache

[^2_8]: https://docs.langchain.com/oss/javascript/integrations/middleware/anthropic

[^2_9]: https://www.firecrawl.dev/blog/using-prompt-caching-with-anthropic

[^2_10]: https://docs.portkey.ai/docs/integrations/llms/anthropic/prompt-caching

[^2_11]: https://reference.langchain.com/javascript/langchain-anthropic/AnthropicCacheControl

[^2_12]: https://www.claudecodecamp.com/p/how-prompt-caching-actually-works-in-claude-code

[^2_13]: https://www.reddit.com/r/Anthropic/comments/1idf7x7/anyone_actually_saving_money_with_claudes_prompt/

[^2_14]: https://docs.pipecat.ai/api-reference/server/services/llm/anthropic

[^2_15]: https://gitlab.osti.gov/genesis/genesis-skills/-/blob/main/skills/anthropic-skills/claude-api/shared/prompt-caching.md
