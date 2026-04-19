# SAP Orchestration API — Deployment-Less Model Access

> **Generated:** 2026-04-18  
> **Context:** Investigation of SAP AI Core Orchestration V2 API and its impact on this proxy

---

## What Changed

SAP has introduced two new approaches that **remove the need for per-model deployments**:

1. **Orchestration Service V2** (`gen_ai_hub.orchestration_v2`) — the current recommended API
2. **Orchestration Service V1** (`gen_ai_hub.orchestration`) — **deprecated** as of 2025

The old pattern required you to deploy each model individually via `POST /v2/lm/deployments` and then route to `{deployment_url}/...`. The new orchestration service uses **a single "orchestration service deployment"** — you only deploy the orchestration service once, and then access any model by name in the request body.

---

## How to Discover Available Models

### Option 1: REST API — `GET /v2/lm/foundation-models`

```
GET {AI_API_URL}/v2/lm/foundation-models
Headers:
  Authorization: Bearer <token>
  AI-Resource-Group: <resource_group>
```

This returns all available foundation models in your subaccount without requiring any model-specific deployments.

### Option 2: SDK Documentation

The full model list is maintained at [SAP Note 3437766](https://me.sap.com/notes/3437766). As of SDK v6.7.0 (April 2026), confirmed available models:

#### LLM Models

| Provider | Model Name | Streaming |
|---|---|---|
| OpenAI | `gpt-4o` | Yes |
| OpenAI | `gpt-4o-mini` | Yes |
| OpenAI | `gpt-4.1` | Yes |
| OpenAI | `gpt-4.1-mini` | Yes |
| OpenAI | `gpt-4.1-nano` | Yes |
| OpenAI | `gpt-5` | Yes |
| OpenAI | `gpt-5-mini` | Yes |
| OpenAI | `gpt-5-nano` | Yes |
| OpenAI | `o1` | No |
| OpenAI | `o3` | Yes |
| OpenAI | `o3-mini` | No |
| OpenAI | `o4-mini` | Yes |
| Anthropic | `anthropic--claude-3-haiku` | Yes |
| Anthropic | `anthropic--claude-3.5-sonnet` | Yes |
| Anthropic | `anthropic--claude-3.7-sonnet` | Yes |
| Anthropic | `anthropic--claude-4-sonnet` | Yes |
| Anthropic | `anthropic--claude-4-opus` | Yes |
| Anthropic | `anthropic--claude-4.5-sonnet` | Yes |
| Anthropic | `anthropic--claude-4.5-haiku` | Yes |
| Google | `gemini-2.0-flash` | Yes |
| Google | `gemini-2.0-flash-lite` | Yes |
| Google | `gemini-2.5-flash` | Yes |
| Google | `gemini-2.5-pro` | Yes |
| Google | `gemini-2.5-flash-lite` | Yes |
| MistralAI | `mistralai--mistral-small-instruct` | No |
| MistralAI | `mistralai--mistral-medium-instruct` | No |
| MistralAI | `mistralai--mistral-large-instruct` | No |
| Amazon | `amazon--nova-lite` | No |
| Amazon | `amazon--nova-micro` | No |
| Amazon | `amazon--nova-pro` | No |
| Amazon | `amazon--amazon--nova-premier` | Yes |
| Cohere | `cohere--command-a-reasoning` | Yes |
| Cohere | `cohere--reranker` | Yes |
| Perplexity | `sonar` | Yes |
| Perplexity | `sonar-pro` | Yes |

#### Embedding Models

| Provider | Model Name |
|---|---|
| Amazon | `amazon--titan-embed-text` |
| Amazon | `amazon--titan-embed-image` |
| Google | `google--gemini-embedding` |
| NVIDIA | `nvidia--llama-3.2-nv-embedqa-1b` |
| OpenAI | `text-embedding-3-small` |
| OpenAI | `text-embedding-3-large` |
| OpenAI | `text-embedding-ada-002` |

---

## How to Access Models (Orchestration V2)

### 1. Prerequisites

Deploy the orchestration service **once** per resource group (not per model):

```
POST {AI_API_URL}/v2/lm/deployments
Headers:
  Authorization: Bearer <token>
  AI-Resource-Group: <resource_group>
Content-Type: application/json

{
  "configurationId": "<orchestration-service-config-id>"
}
```

Once running, a single orchestration deployment URL handles **all models**.

### 2. SDK Usage — Python (sap-ai-sdk-gen)

Install:

```bash
pip install "sap-ai-sdk-gen[all]"
```

Configure (`~/.aicore/config.json`):

```json
{
  "AICORE_AUTH_URL": "https://<tenant>.authentication.sap.hana.ondemand.com/oauth/token",
  "AICORE_CLIENT_ID": "<client_id>",
  "AICORE_CLIENT_SECRET": "<client_secret>",
  "AICORE_RESOURCE_GROUP": "<resource_group>",
  "AICORE_BASE_URL": "https://api.ai.<region>.cfapps.sap.hana.ondemand.com/v2"
}
```

Basic usage — specify any model by name, no deployment ID needed:

```python
from gen_ai_hub.orchestration_v2.models.llm_model_details import LLMModelDetails
from gen_ai_hub.orchestration_v2.models.message import SystemMessage, UserMessage
from gen_ai_hub.orchestration_v2.models.template import Template, PromptTemplatingModuleConfig
from gen_ai_hub.orchestration_v2.models.config import ModuleConfig, OrchestrationConfig
from gen_ai_hub.orchestration_v2.service import OrchestrationService

# Specify model by name — no deployment ID needed
llm = LLMModelDetails(name="gpt-4o", params={"max_completion_tokens": 512})

template = Template(template=[
    SystemMessage(content="You are a helpful assistant."),
    UserMessage(content="{{?user_query}}"),
])

prompt_template = PromptTemplatingModuleConfig(prompt=template, model=llm)
module_config = ModuleConfig(prompt_templating=prompt_template)
config = OrchestrationConfig(modules=module_config)

# OrchestrationService auto-finds the running orchestration deployment
service = OrchestrationService(config=config)
result = service.run(placeholder_values={"user_query": "Hello!"})
print(result.final_result.choices[0].message.content)
```

Streaming:

```python
from gen_ai_hub.orchestration_v2.models.streaming import GlobalStreamOptions

config_stream = OrchestrationConfig(
    modules=module_config,
    stream=GlobalStreamOptions(enabled=True)
)
service = OrchestrationService(config=config_stream)
for chunk in service.stream(placeholder_values={"user_query": "Hello!"}):
    print(chunk.final_result.choices[0].delta.content, end="")
```

### 3. Deployment Resolution Options

The `OrchestrationService` resolves which deployment to target via:

| Parameter | Behavior |
|---|---|
| _(none)_ | Auto-finds the most recent `RUNNING` deployment |
| `api_url=<url>` | Targets exact deployment URL |
| `deployment_id=<id>` | Targets deployment by ID |
| `config_id=<id>` | Finds `RUNNING` deployment by configuration ID |
| `config_name=<name>` | Finds `RUNNING` deployment by configuration name |

### 4. Raw HTTP Request (no SDK)

The underlying REST endpoint:

```
POST {orchestration_deployment_url}/completion
Headers:
  Authorization: Bearer <token>
  AI-Resource-Group: <resource_group>
Content-Type: application/json

{
  "orchestration_config": {
    "module_configurations": {
      "llm_module_config": {
        "model_name": "gpt-4o",
        "model_params": {
          "max_tokens": 512
        }
      },
      "templating_module_config": {
        "template": [
          {"role": "system", "content": "You are a helpful assistant."},
          {"role": "user",   "content": "{{?user_query}}"}
        ]
      }
    }
  },
  "input_params": {
    "user_query": "Hello!"
  }
}
```

Streaming variant — add `"stream": true` to the root JSON body, responses are SSE (`text/event-stream`).

---

## Impact on This Proxy Codebase

### Current Architecture (old model)

| Step | What happens |
|---|---|
| Startup | `GET /v2/lm/deployments` — enumerate all running deployments per subaccount |
| Model resolution | Match model name → deployment URL (cached for 7 days) |
| Inference | `POST {deployment_url}/{model-specific-path}` (e.g. `/converse`, `/invoke`, `/chat/completions`) |

Relevant code: `utils/sdk_utils.py:277` (`fetch_all_deployments`), `config/config_parser.py:318` (`_auto_discover_deployments`)

### New Architecture (orchestration V2)

| Step | What happens |
|---|---|
| Startup | `GET /v2/lm/foundation-models` — enumerate all available model names |
| Model resolution | Model name passed directly in request body |
| Inference | `POST {orchestration_deployment_url}/completion` — single endpoint for all models |

### Required Changes

1. **Model discovery**: replace `GET /v2/lm/deployments` with `GET /v2/lm/foundation-models`
2. **Config simplification**: no more `deployment_ids` or `model_to_deployment_urls` mappings in config JSON
3. **Single inference endpoint**: all models routed to `{orchestration_url}/completion`
4. **Format conversion**: orchestration service returns OpenAI-compatible JSON natively — most of `proxy_helpers.py` converters become unnecessary
5. **Deployment management**: only the orchestration service deployment needs to be discovered (one per resource group)

### Branch Status

An unmerged branch `feat/sap-ai-orchestration-model-discovery` exists in the remote (seen in `.git/FETCH_HEAD`) but has not been merged into `main`.

---

## SDK Package Reference

| Package | Status | Notes |
|---|---|---|
| `generative-ai-hub-sdk` | **Deprecated / Archived** | Last version 4.12.4 (May 2025) |
| `sap-ai-sdk-gen` | **Active** | Current package, v6.7.0 (March 2026) |

Install:

```bash
pip install "sap-ai-sdk-gen[all]"
```

Docs: https://help.sap.com/doc/generative-ai-hub-sdk/CLOUD/en-US/index.html
