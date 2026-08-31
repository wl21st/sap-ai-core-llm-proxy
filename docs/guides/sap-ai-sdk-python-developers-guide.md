---
title: SAP Cloud SDK for AI (Python) Developer's Guide
aliases:
  - SAP AI Core Python SDK Guide
  - sap-ai-sdk-gen Guide
tags:
  - sap-ai-core
  - generative-ai
  - python
  - anthropic
  - openai
  - orchestration
sdk_version: 7.2.0
---

# SAP Cloud SDK for AI (Python) Developer's Guide

An implementation-focused guide to `sap-ai-sdk-gen` for consuming Anthropic Claude and OpenAI models through SAP AI Core Generative AI Hub. It covers direct model access, LangChain, Orchestration Service V2, deployment resolution, streaming, usage accounting, prompt caching, tool calling, and production patterns.

> [!IMPORTANT]
> SAP renamed the former Generative AI Hub SDK to **SAP Cloud SDK for AI (Python)**. The distribution is `sap-ai-sdk-gen`; the Python import namespace remains `gen_ai_hub`.

## Contents

- [1. Mental model](#1-mental-model)
- [2. Install and configure](#2-install-and-configure)
- [3. Choose an access layer](#3-choose-an-access-layer)
- [4. Deployment model](#4-deployment-model)
- [5. OpenAI models](#5-openai-models)
- [6. Anthropic Claude models](#6-anthropic-claude-models)
- [7. LangChain and model portability](#7-langchain-and-model-portability)
- [8. Orchestration Service V2](#8-orchestration-service-v2)
- [9. Streaming](#9-streaming)
- [10. Token usage and caching](#10-token-usage-and-caching)
- [11. Tools, function calling, and skills](#11-tools-function-calling-and-skills)
- [12. Enterprise modules](#12-enterprise-modules)
- [13. Async, retries, and resource management](#13-async-retries-and-resource-management)
- [14. Production checklist](#14-production-checklist)
- [15. Troubleshooting](#15-troubleshooting)
- [16. References](#16-references)

## 1. Mental model

SAP AI Core provides the governed control plane: OAuth authentication, resource groups, model and orchestration deployments, quotas, and deployment URLs. Generative AI Hub provides access to foundation models from several vendors. `sap-ai-sdk-gen` adds familiar client interfaces over those SAP-managed endpoints.

There are three useful layers:

| Layer | Python namespace | Best for | Main trade-off |
|---|---|---|---|
| Provider-native | `gen_ai_hub.proxy.native.*` | Provider-specific features and wire-level control | Different request/response shapes |
| LangChain | `gen_ai_hub.proxy.langchain` | Portable chains, agents, and common `invoke`/`stream` APIs | Provider-specific features may be hidden or unavailable |
| Orchestration V2 | `gen_ai_hub.orchestration_v2` | Templating, masking, filtering, translation, grounding, fallbacks, and a harmonized response | Requires an Orchestration deployment |

The SDK is not an independent model host. A successful call still requires:

1. A service key or equivalent credentials for SAP AI Core.
2. The target resource group in which the deployment is visible.
3. A `RUNNING` direct-model deployment or Orchestration deployment.
4. A model name that is enabled and available in the tenant's Generative AI Hub catalog.

Model availability and feature support are tenant- and model-dependent. Treat the supported-model list in the installed SDK and SAP documentation as the source of truth rather than hard-coding assumptions from another tenant.

## 2. Install and configure

### 2.1 Install the package

The default package includes OpenAI support and LangChain integration. Add `amazon` for Claude through the Bedrock-compatible client. Use `all` when the application needs OpenAI, Amazon, Google, and all corresponding integrations.

```bash
python -m pip install sap-ai-sdk-gen
python -m pip install "sap-ai-sdk-gen[amazon]"
# Or:
python -m pip install "sap-ai-sdk-gen[all]"
```

Pin and test the SDK version in production. This guide was checked against `sap-ai-sdk-gen 7.2.0`.

### 2.2 Configure with environment variables

```bash
export AICORE_AUTH_URL="https://YOUR_SUBDOMAIN.authentication.sap.hana.ondemand.com/oauth/token"
export AICORE_CLIENT_ID="YOUR_CLIENT_ID"
export AICORE_CLIENT_SECRET="YOUR_CLIENT_SECRET"
export AICORE_BASE_URL="https://api.ai.YOUR_REGION.hana.ondemand.com/v2"
export AICORE_RESOURCE_GROUP="default"
```

The SDK also supports X.509 authentication:

```bash
export AICORE_AUTH_URL="https://YOUR_SUBDOMAIN.authentication.cert.sap.hana.ondemand.com"
export AICORE_CLIENT_ID="YOUR_CLIENT_ID"
export AICORE_CERT_FILE_PATH="/secure/path/client-cert.pem"
export AICORE_KEY_FILE_PATH="/secure/path/client-key.pem"
```

Do not commit secrets or put them in source code. In deployed applications, inject them through a secret manager or the platform binding.

### 2.3 Configure with `~/.aicore/config.json`

```json
{
  "AICORE_AUTH_URL": "https://YOUR_SUBDOMAIN.authentication.sap.hana.ondemand.com/oauth/token",
  "AICORE_CLIENT_ID": "YOUR_CLIENT_ID",
  "AICORE_CLIENT_SECRET": "YOUR_CLIENT_SECRET",
  "AICORE_RESOURCE_GROUP": "default",
  "AICORE_BASE_URL": "https://api.ai.YOUR_REGION.hana.ondemand.com/v2"
}
```

Configuration precedence is environment variables, profile/config file, then `VCAP_SERVICES` when present. The configuration directory can be changed with `AICORE_HOME`; a specific file can be selected with `AICORE_CONFIG`. Profiles use `AICORE_PROFILE` and files named `config_<profile>.json`.

### 2.4 Explicit proxy client

Explicit construction is useful for tests, multiple subaccounts, or applications that do not use the default profile.

```python
from gen_ai_hub.proxy import get_proxy_client

proxy_client = get_proxy_client(
    proxy_version="gen-ai-hub",
    base_url="https://api.ai.YOUR_REGION.hana.ondemand.com",
    auth_url="https://YOUR_SUBDOMAIN.authentication.sap.hana.ondemand.com",
    client_id="YOUR_CLIENT_ID",
    client_secret="YOUR_CLIENT_SECRET",
    resource_group="default",
)
```

Pass `proxy_client=proxy_client` to native or LangChain clients when you need deterministic credential selection. Never log the proxy client, access token, or client secret.

## 3. Choose an access layer

Use provider-native access when you need the exact OpenAI or Bedrock contract, provider-specific parameters, or raw response metadata. Use LangChain when the application is already built around chains or agents. Use Orchestration V2 when governance modules should be part of the request pipeline instead of being implemented separately in application code.

The same model can therefore be reached in different ways:

```python
# OpenAI-compatible native client
from gen_ai_hub.proxy.native.openai import chat

# Anthropic Claude through the Bedrock-compatible native client
from gen_ai_hub.proxy.native.amazon import Session

# Harmonized LangChain model
from gen_ai_hub.proxy.langchain import init_llm

# SAP Orchestration Service V2
from gen_ai_hub.orchestration_v2 import OrchestrationService
```

## 4. Deployment model

### 4.1 Direct model deployment versus Orchestration deployment

There are two operational paths:

- **Direct model access:** deploy or provision the selected foundation model, then invoke its model-specific endpoint. The SDK resolves a deployment by `model_name`, `model_version`, or an explicit `deployment_id`.
- **Orchestration access:** deploy the `orchestration` scenario/executable, then send a harmonized completion request to that deployment. The underlying LLM is selected inside the orchestration configuration.

The orchestration deployment is not the same thing as a Claude or GPT deployment. An Orchestration request still names the model, but the request goes first to the orchestration service, where modules and policy controls run.

### 4.2 Create an Orchestration configuration and deployment

Use AI Launchpad for the guided workflow, or the AI Core SDK for automation. The exact model and service availability depend on the tenant.

```python
from ai_core_sdk.ai_core_v2_client import AICoreV2Client

ai_core = AICoreV2Client(
    base_url="https://api.ai.YOUR_REGION.hana.ondemand.com/v2",
    auth_url="https://YOUR_SUBDOMAIN.authentication.sap.hana.ondemand.com/oauth/token",
    client_id="YOUR_CLIENT_ID",
    client_secret="YOUR_CLIENT_SECRET",
    resource_group="default",
)

configuration = ai_core.configuration.create(
    name="production-orchestration",
    scenario_id="orchestration",
    executable_id="orchestration",
    resource_group="default",
)

deployment = ai_core.deployment.create(
    configuration_id=configuration.id,
    resource_group="default",
)

print(configuration.id, deployment.id)
```

Poll the deployment until it is `RUNNING` before sending traffic. Keep the deployment ID in environment-specific configuration, not in application logic. Deployment URLs can change when a deployment is recreated; resolving by deployment ID or configuration reference is safer than copying a temporary URL into source code.

### 4.3 Deployment selection and precedence

Native SDK calls accept selectors such as:

```python
response = chat.completions.create(
    model_name="gpt-4o",
    model_version="latest",
    messages=[{"role": "user", "content": "Hello"}],
)

# Or select one known deployment explicitly:
response = chat.completions.create(
    deployment_id="YOUR_DEPLOYMENT_ID",
    messages=[{"role": "user", "content": "Hello"}],
)
```

For Orchestration V2, `OrchestrationService` can receive `api_url`, `deployment_id`, `config_id`, or `config_name`. If no explicit selector is supplied, the SDK looks for a running orchestration deployment and selects the most recently started matching deployment. Explicit selection is recommended for production isolation.

## 5. OpenAI models

### 5.1 Native chat completions

```python
from gen_ai_hub.proxy.native.openai import chat

messages = [
    {"role": "system", "content": "You are a precise SAP integration assistant."},
    {"role": "user", "content": "What is a resource group in SAP AI Core?"},
]

response = chat.completions.create(
    model_name="gpt-4o",
    messages=messages,
    temperature=0.2,
    max_tokens=400,
)

print(response.choices[0].message.content)
if response.usage:
    print(response.usage.prompt_tokens, response.usage.completion_tokens)
```

The SDK follows the OpenAI-compatible object model. Prefer the parameter supported by the selected model and SDK version. Newer OpenAI models may prefer `max_completion_tokens` over the older `max_tokens` parameter.

### 5.2 Responses API

For models and tenants that expose the Responses API through the SDK:

```python
from gen_ai_hub.proxy.native.openai import responses

result = responses.create(
    model="gpt-5",
    instructions="You are a helpful assistant.",
    input="Explain SAP AI Core resource groups in two sentences.",
)

print(result.output_text)
```

Use chat completions when an existing application depends on messages and choices. Use Responses when you want the newer OpenAI response abstraction and supported built-in response features.

### 5.3 Typed structured output

```python
from pydantic import BaseModel
from gen_ai_hub.proxy.native.openai import chat


class DeploymentSummary(BaseModel):
    deployment_id: str
    status: str
    recommendation: str


result = chat.completions.parse(
    model_name="gpt-4o",
    messages=[
        {
            "role": "user",
            "content": "Return a sample deployment summary for deployment d-123 that is RUNNING.",
        }
    ],
    response_format=DeploymentSummary,
)

summary = result.choices[0].message.parsed
print(summary.deployment_id, summary.status)
```

Structured output is a contract, not a substitute for validation. Check the parsed object, handle refusal or incomplete output, and keep the schema small enough for the target model.

### 5.4 OpenAI streaming

```python
from gen_ai_hub.proxy.native.openai import chat


stream = chat.completions.create(
    model_name="gpt-4o",
    messages=[{"role": "user", "content": "Give three SAP AI Core deployment tips."}],
    max_tokens=250,
    stream=True,
    stream_options={"include_usage": True},
)

for chunk in stream:
    if chunk.choices:
        delta = chunk.choices[0].delta
        if delta.content:
            print(delta.content, end="", flush=True)
    if chunk.usage:
        print("usage=", chunk.usage)
```

Do not assume the final chunk contains text. A stream can contain role-only chunks, tool-call deltas, a finish reason, and a usage-only chunk. Buffer tool-call arguments separately from text.

## 6. Anthropic Claude models

The Python SDK exposes Claude through the Amazon/Bedrock-compatible integration. That is intentional: SAP AI Core routes Anthropic models through the Bedrock contract. The client object is therefore created with `gen_ai_hub.proxy.native.amazon.Session`, not an Anthropic API key.

### 6.1 Claude with Bedrock Converse

```python
from gen_ai_hub.proxy.native.amazon import Session

session = Session()
bedrock = session.client(model_name="anthropic--claude-4.5-sonnet")

response = bedrock.converse(
    messages=[
        {
            "role": "user",
            "content": [{"text": "Explain SAP AI Core resource groups to a new developer."}],
        }
    ],
    system=[{"text": "Be concise and use one practical example."}],
    inferenceConfig={
        "maxTokens": 600,
        "temperature": 0.2,
        "topP": 0.9,
    },
)

print(response["output"]["message"]["content"][0].get("text", ""))
print(response.get("stopReason"))
print(response.get("usage"))
```

Converse uses Bedrock names such as `maxTokens` and `inferenceConfig`. Do not copy OpenAI parameter names into this payload without checking the target contract.

### 6.2 Claude with the Anthropic Messages wire format

Some Claude features and older model deployments use the Anthropic Messages body through `invoke`:

```python
import json
from gen_ai_hub.proxy.native.amazon import Session

bedrock = Session().client(model_name="anthropic--claude-3.7-sonnet")
body = {
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 600,
    "system": "You are a careful SAP platform engineer.",
    "messages": [
        {"role": "user", "content": [{"type": "text", "text": "What is an orchestration deployment?"}]}
    ],
}

response = bedrock.invoke_model(body=json.dumps(body))
payload = json.loads(response["body"].read())
print("".join(block.get("text", "") for block in payload.get("content", [])))
print(payload.get("usage"))
```

Use the method supported by the model deployment. The SDK documentation specifically notes that some Amazon Nova models support `converse` but not `invoke` or `invoke_model_with_response_stream`. Check the model support table before choosing the method.

### 6.3 Claude streaming

```python
import json
from gen_ai_hub.proxy.native.amazon import Session

bedrock = Session().client(model_name="anthropic--claude-4.5-sonnet")
body = json.dumps({
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 500,
    "messages": [{"role": "user", "content": "Stream a short explanation of prompt caching."}],
})

response = bedrock.invoke_model_with_response_stream(body=body)
for event in response.get("body", []):
    chunk = json.loads(event["chunk"]["bytes"])
    if chunk.get("type") == "content_block_delta":
        print(chunk.get("delta", {}).get("text", ""), end="", flush=True)
```

Claude event streams include metadata and lifecycle events as well as text deltas. Production consumers should handle `message_start`, `content_block_start`, `content_block_delta`, `content_block_stop`, `message_delta`, and `message_stop` rather than assuming every event contains text.

## 7. LangChain and model portability

### 7.1 Harmonized initialization

```python
from gen_ai_hub.proxy.langchain import init_llm

llm = init_llm(
    model_name="anthropic--claude-4.5-sonnet",
    max_tokens=500,
    temperature=0.2,
)

answer = llm.invoke("Summarize the purpose of an AI Core resource group.")
print(answer.content if hasattr(answer, "content") else answer)
```

The same shape works for an OpenAI model:

```python
llm = init_llm(model_name="gpt-4o", max_tokens=500, temperature=0.2)
```

### 7.2 Prompt chains

```python
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from gen_ai_hub.proxy.langchain import init_llm

prompt = ChatPromptTemplate.from_messages([
    ("system", "You explain SAP platform concepts to Python developers."),
    ("user", "Explain {topic} using one analogy and one code-oriented example."),
])
llm = init_llm(model_name="gpt-4o", temperature=0.1, max_tokens=450)
chain = prompt | llm | StrOutputParser()

print(chain.invoke({"topic": "deployment resolution"}))
```

### 7.3 LangChain streaming and tools

```python
for chunk in chain.stream({"topic": "resource groups"}):
    print(chunk, end="", flush=True)
```

For an agent, bind tools only when the selected model and integration support tool calls:

```python
from langchain_core.tools import tool
from gen_ai_hub.proxy.langchain import init_llm


@tool
def deployment_status(deployment_id: str) -> str:
    """Return the status of an allowed deployment ID."""
    # Replace with a call to a trusted internal service.
    return f"status for {deployment_id}: RUNNING"


model = init_llm(model_name="gpt-4o", temperature=0).bind_tools([deployment_status])
result = model.invoke("Check deployment d-123.")
print(result.tool_calls if hasattr(result, "tool_calls") else result.content)
```

Tool binding only describes tools to the model. The application remains responsible for authorization, argument validation, execution, timeouts, and returning the tool result to the model.

## 8. Orchestration Service V2

Orchestration V2 is the preferred orchestration API. The older `gen_ai_hub.orchestration` API is deprecated and is scheduled for decommissioning in October 2026 according to SAP documentation.

### 8.1 A minimal V2 pipeline

```python
from gen_ai_hub.orchestration_v2 import (
    LLMModelDetails,
    ModuleConfig,
    OrchestrationConfig,
    OrchestrationService,
    PromptTemplatingModuleConfig,
    SystemMessage,
    Template,
    UserMessage,
)

template = Template(
    template=[
        SystemMessage(content="You are a helpful SAP platform assistant."),
        UserMessage(content="Explain {{?topic}} in three bullet points."),
    ],
    defaults={"topic": "SAP AI Core resource groups"},
)

config = OrchestrationConfig(
    modules=ModuleConfig(
        prompt_templating=PromptTemplatingModuleConfig(
            prompt=template,
            model=LLMModelDetails(
                name="anthropic--claude-4.5-sonnet",
                params={"max_tokens": 500, "temperature": 0.2},
            ),
        )
    )
)

service = OrchestrationService(
    config=config,
    deployment_id="YOUR_ORCHESTRATION_DEPLOYMENT_ID",
)
result = service.run(placeholder_values={"topic": "deployment model"})

print(result.final_result.choices[0].message.content)
print(result.final_result.usage)
```

`LLMModelDetails.params` is provider/model-specific. For OpenAI models, parameters commonly use `max_completion_tokens`; for Claude through orchestration, use the parameters accepted by the orchestration service and model version. Validate the resulting request against the tenant's model configuration.

### 8.2 OpenAI through Orchestration

Only the model name changes:

```python
llm = LLMModelDetails(
    name="gpt-4o",
    params={"max_completion_tokens": 500, "temperature": 0.1},
)
```

This gives OpenAI model access while keeping the prompt template and optional governance modules in the same pipeline.

### 8.3 Message history

Orchestration does not own application conversation state. Store history in the application and pass it back on each request.

```python
history = []

first = service.run(
    placeholder_values={"topic": "resource groups"},
    history=history,
)
assistant_message = first.final_result.choices[0].message
history = (first.intermediate_results.templating or []) + [assistant_message]

second = service.run(
    placeholder_values={"topic": "deployment URLs"},
    history=history,
)
print(second.final_result.choices[0].message.content)
```

Keep histories bounded. Summarize or truncate old turns before the prompt exceeds the model context window, and do not place credentials or untrusted instructions in a system message without deliberate handling.

### 8.4 Prompt Registry references

A prompt or orchestration configuration can be versioned centrally in Prompt Registry and referenced by ID or scenario/name/version.

```python
from gen_ai_hub.orchestration_v2 import (
    CompletionRequestConfigurationReferenceByNameScenarioVersionConfigRef,
    OrchestrationService,
)

config_ref = CompletionRequestConfigurationReferenceByNameScenarioVersionConfigRef(
    scenario="production",
    name="sap-support-assistant",
    version="1.2.0",
)

service = OrchestrationService(
    config_ref=config_ref,
    deployment_id="YOUR_ORCHESTRATION_DEPLOYMENT_ID",
)
result = service.run(placeholder_values={"product": "SAP S/4HANA"})
```

Do not pass both `config` and `config_ref`. Use registry versions to make prompt changes auditable and rollbacks possible.

### 8.5 Orchestration response inspection

The final response follows an OpenAI-like shape, but the response also exposes intermediate module results:

```python
final = result.final_result
print(final.choices[0].message.content)
print(final.choices[0].finish_reason)
print(final.usage.prompt_tokens, final.usage.completion_tokens)

modules = result.intermediate_results
if modules.input_masking:
    print("input masking ran", modules.input_masking.message)
if modules.output_filtering:
    print("output filtering ran", modules.output_filtering.message)
if modules.grounding:
    print("grounding ran", modules.grounding.message)
```

Use intermediate results for observability and audit decisions, but avoid logging raw PII, prompts, or retrieved documents by default.

## 9. Streaming

### 9.1 Orchestration V2 streaming

Set `GlobalStreamOptions(enabled=True)` and call `stream`, not `run`.

```python
from gen_ai_hub.orchestration_v2 import GlobalStreamOptions

streaming_config = config.model_copy(
    update={"stream": GlobalStreamOptions(enabled=True, chunk_size=100)}
)

for chunk in service.stream(
    config=streaming_config,
    placeholder_values={"topic": "streaming responses"},
):
    choices = chunk.final_result.choices
    if choices and choices[0].delta.content:
        print(choices[0].delta.content, end="", flush=True)
```

The SDK enforces that the config stream flag matches the function used. A config with streaming enabled must be passed to `stream`; a non-streaming config must be passed to `run`.

The stream response uses `delta`, not `message`. The final usage may arrive in a later chunk, and module-level filtering or translation can buffer content. Do not treat the first token as proof that the entire pipeline has completed.

### 9.2 Async streaming

```python
import asyncio


async def main() -> None:
    async_service = service
    stream = await async_service.astream(
        config=streaming_config,
        placeholder_values={"topic": "async streaming"},
    )
    async for chunk in stream:
        choices = chunk.final_result.choices
        if choices and choices[0].delta.content:
            print(choices[0].delta.content, end="", flush=True)


asyncio.run(main())
```

Close long-lived async clients during application shutdown. If a client framework owns the event loop, use its lifecycle hooks rather than calling `asyncio.run` inside a request handler.

## 10. Token usage and caching

### 10.1 Usage fields

OpenAI-compatible and Orchestration V2 responses commonly expose:

```text
prompt_tokens
completion_tokens
total_tokens
prompt_tokens_details.cached_tokens
completion_tokens_details.reasoning_tokens
```

Anthropic Messages/Bedrock responses commonly expose provider-specific usage such as `input_tokens`, `output_tokens`, and cache fields. Bedrock Converse uses its own response shape. Capture the raw provider response when billing or audit accuracy matters, then normalize it at the application boundary.

```python
def read_openai_usage(response) -> dict[str, int]:
    usage = response.usage
    if usage is None:
        return {}
    return {
        "input_tokens": usage.prompt_tokens,
        "output_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
        "cached_tokens": getattr(
            getattr(usage, "prompt_tokens_details", None), "cached_tokens", 0
        ) or 0,
        "reasoning_tokens": getattr(
            getattr(usage, "completion_tokens_details", None), "reasoning_tokens", 0
        ) or 0,
    }
```

Do not calculate cost from `total_tokens` alone when cached, reasoning, audio, or provider-specific token categories affect billing. Store provider, model, deployment, resource group, request ID, finish reason, and all usage subfields you receive.

### 10.2 Prompt caching with Claude

Anthropic prompt caching is a provider feature. A cache marker is placed on a content block in the Anthropic Messages payload:

```python
body = {
    "anthropic_version": "bedrock-2023-05-31",
    "max_tokens": 400,
    "system": [
        {
            "type": "text",
            "text": "A long stable system prompt and policy document...",
            "cache_control": {"type": "ephemeral"},
        }
    ],
    "messages": [
        {"role": "user", "content": [{"type": "text", "text": "Answer the question."}]}
    ],
}
```

Put stable, reusable content before changing user content. Cache markers do not make arbitrary text permanently cached; the provider decides eligibility and TTL. The first request may report cache creation tokens; later requests may report cache read tokens. Confirm the actual response usage and tenant pricing before claiming savings.

The SDK's native client generally passes provider payloads through, but support varies by client layer and model. Orchestration modules can transform prompts, so verify that cache markers survive the selected path before relying on cache hits. LangChain caching options documented for some integrations are not the same as Anthropic prompt caching, and SDK documentation notes that some model caching is not supported for streaming methods.

### 10.3 Normalize usage defensively

```python
def normalize_anthropic_usage(usage: dict) -> dict[str, int]:
    cache_creation = usage.get("cache_creation") or {}
    created = usage.get("cache_creation_input_tokens")
    if created is None:
        created = (
            cache_creation.get("ephemeral_5m_input_tokens", 0)
            + cache_creation.get("ephemeral_1h_input_tokens", 0)
        )
    return {
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "cache_creation_input_tokens": created or 0,
        "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
    }
```

Provider wire schemas can evolve. Preserve the raw `usage` object alongside normalized fields so a new nested field does not silently disappear from financial records.

## 11. Tools, function calling, and skills

### 11.1 Orchestration V2 function tools

Orchestration V2 includes `FunctionTool` and a `function_tool` decorator. Type hints are used to generate a JSON Schema.

```python
import json
from gen_ai_hub.orchestration_v2 import function_tool


@function_tool(strict=True)
def get_deployment_status(deployment_id: str) -> str:
    """Return the status of a deployment after authorization checks."""
    allowed = {"d-123"}
    if deployment_id not in allowed:
        raise ValueError("deployment is not allowed")
    return "RUNNING"


tool = get_deployment_status
template = Template(
    template=[UserMessage(content="Check deployment d-123 and summarize the result.")],
    tools=[tool],
)
```

Add the template to `PromptTemplatingModuleConfig` as in the previous orchestration example. The function definition is sent to the model; it is not automatically executed by the service.

### 11.2 Execute a synchronous tool call

The model can return an assistant message with `tool_calls`. Execute only calls that pass authorization and schema validation, then append the assistant call and a `ToolChatMessage` to history before calling the model again.

```python
import json
from gen_ai_hub.orchestration_v2 import ToolChatMessage


response = service.run(config=config, placeholder_values={"topic": "deployment status"})
message = response.final_result.choices[0].message

if message.tool_calls:
    history = [message]
    for call in message.tool_calls:
        args = call.function.parse_arguments()
        # Look up the tool by name, validate args, and execute in a sandbox.
        output = get_deployment_status.execute(**args)
        history.append(
            ToolChatMessage(tool_call_id=call.id, content=json.dumps(output))
        )
    final = service.run(config=config, history=history)
    print(final.final_result.choices[0].message.content)
```

The abbreviated example omits the original user/template history for clarity. In a real conversation, preserve the complete ordered sequence: user message, assistant tool-call message, tool result message, then the follow-up request.

### 11.3 Streaming tool calls

Streaming tool calls can be split across chunks. Buffer by tool-call index and concatenate the JSON argument strings before parsing.

```python
tool_buffers: dict[int, dict[str, str]] = {}

for chunk in service.stream(config=streaming_config):
    choices = chunk.final_result.choices
    if not choices:
        continue
    for call in choices[0].delta.tool_calls or []:
        entry = tool_buffers.setdefault(
            call.index, {"id": call.id or "", "name": "", "arguments": ""}
        )
        if call.id:
            entry["id"] = call.id
        if call.function:
            entry["name"] += call.function.name or ""
            entry["arguments"] += call.function.arguments or ""

# Only now parse and validate each complete argument string.
```

Never execute a partial argument fragment. Treat model-generated JSON as untrusted input; use Pydantic or an equivalent schema validator, enforce allowed resource IDs and operations, and apply a deadline.

### 11.4 What "skills" means here

`skills` is not a first-class `sap-ai-sdk-gen` request parameter. Implement skills as an application-level composition of:

- A versioned prompt template in Orchestration/Prompt Registry.
- One or more narrowly scoped tools with JSON Schemas.
- An authorization policy and execution service.
- Optional grounding, masking, filtering, or translation modules.
- Conversation state and an explicit tool-call loop.

This separation matters: the model can select a tool, but it must not receive unrestricted Python execution, network access, database credentials, or arbitrary deployment-management permissions.

## 12. Enterprise modules

Orchestration V2's `ModuleConfig` can combine prompt templating with filtering, masking, grounding, and translation.

```python
from gen_ai_hub.orchestration_v2 import (
    DPIStandardEntity,
    MaskingMethod,
    MaskingModuleConfig,
    MaskingProviderConfig,
    ProfileEntity,
)

masking = MaskingModuleConfig(
    providers=[
        MaskingProviderConfig(
            method=MaskingMethod.ANONYMIZATION,
            entities=[
                DPIStandardEntity(type=ProfileEntity.EMAIL),
                DPIStandardEntity(type=ProfileEntity.PERSON),
                DPIStandardEntity(type=ProfileEntity.PHONE),
            ],
            allowlist=["SAP"],
        )
    ]
)

secure_config = OrchestrationConfig(
    modules=ModuleConfig(
        prompt_templating=prompt_template_config,
        masking=masking,
    )
)
```

Use input filtering to reject unsafe requests and output filtering to prevent unsafe responses. Use masking when the model does not need the original PII. Use grounding for retrieval-backed answers, and inspect the grounding intermediate result for citations or retrieved context according to the configured module.

Modules have operational consequences: they add latency, can change token counts, can buffer streaming output, and can reject a request. Include module outcomes in telemetry and test the exact model/module combination.

## 13. Async, retries, and resource management

### 13.1 Orchestration retries

For orchestration calls, the SDK provides retry helpers that use exponential backoff with jitter for retryable failures such as rate limiting:

```python
result = service.run_with_retries(
    config=config,
    placeholder_values={"topic": "retry behavior"},
    max_retries=4,
    base_delay=1.0,
)
```

Retries are not automatically safe for every operation. A generation request may be duplicated after a timeout, and a tool loop may repeat a side effect. Use idempotency keys in downstream services and retry only requests whose business semantics permit it.

### 13.2 Async calls

```python
result = await service.arun(
    config=config,
    placeholder_values={"topic": "async orchestration"},
)
```

Use `arun_with_retries` and `astream` for asynchronous equivalents. Bound concurrency with an application semaphore, configure an explicit timeout, and avoid creating a new SDK session per request.

### 13.3 Reuse clients

Constructing sessions and proxy clients is more expensive than reusing them. Create them at application startup or cache them per credential/resource-group/model combination. In multi-tenant services, do not accidentally share one client across resource groups.

## 14. Production checklist

### Authentication and tenancy

- Store service keys, client secrets, certificates, and tokens in a secret manager.
- Set and verify `AICORE_RESOURCE_GROUP` explicitly.
- Use separate deployments and credentials for development, test, and production where required.
- Do not log authorization headers or complete prompts by default.

### Model and deployment

- Confirm the model name exactly as registered in Generative AI Hub.
- Confirm the model's supported method: OpenAI chat, Responses, Bedrock Converse, invoke, or stream.
- Resolve a known deployment ID or configuration reference in production.
- Poll for `RUNNING` before sending traffic and alert on deployment state changes.

### Reliability

- Set connect, read, and total request timeouts.
- Retry 429 and transient failures with bounded exponential backoff and jitter.
- Do not retry non-idempotent tools without an idempotency strategy.
- Handle partial streams and disconnects; a stream cannot change its HTTP status after output begins.
- Reuse sessions and cap concurrent requests.

### Usage and cost

- Record model, deployment, resource group, request ID, finish reason, latency, and raw usage fields.
- Separate input, output, cached, cache creation, and reasoning tokens where supplied.
- Validate prompt-cache hit rates from response usage rather than assuming a hit.
- Keep stable prompt prefixes stable if using Claude prompt caching.

### Tool and data safety

- Validate every model-generated tool argument against a strict schema.
- Authorize resource IDs and operations server-side.
- Apply timeouts, quotas, and audit logging to tools.
- Treat retrieved documents and tool output as untrusted content.
- Mask PII before model invocation where possible, and test unmasking behavior.

## 15. Troubleshooting

### `No credentials found in any source`

Check that the environment variables are present in the same process that imports or initializes the SDK. Verify the config file path, profile name, and that `AICORE_BASE_URL` points to the AI Core API base with `/v2` as documented.

### `401` or `403`

Check client credentials, token-service URL, resource-group membership, and deployment visibility. A valid token for one resource group does not imply access to another. If using an explicit proxy client, verify that its `resource_group` is correct.

### Deployment not found

Confirm the deployment is `RUNNING`, the deployment belongs to the selected resource group, and the selector is correct. For Orchestration, ensure the deployment uses the orchestration scenario/executable rather than a direct foundation-model configuration.

### Invalid request parameter

Provider contracts differ. `temperature`, `max_tokens`, and tool schemas are not interchangeable across OpenAI chat, OpenAI Responses, Bedrock Converse, Anthropic Messages, and Orchestration. Start with the SDK example for the exact method and model, then add parameters one at a time.

### Empty streaming chunks

This is normal for lifecycle, role, finish, or usage events. Check for content before printing and handle the final usage/finish event separately. For tool calls, buffer deltas by index.

### Cache tokens remain zero

Check model support, minimum cacheable context, exact placement of `cache_control`, stable prefix reuse, and whether the selected SDK layer preserves the provider block. Streaming support and orchestration modules may have different caching behavior. Inspect raw usage from two sequential requests.

## 16. References

- [SAP Cloud SDK for AI (Python) overview](https://sap.github.io/ai-sdk/docs/python/overview)
- [SAP official Python SDK repository](https://github.com/SAP/ai-sdk-python)
- [Native client integrations](https://help.sap.com/doc/generative-ai-hub-sdk/CLOUD/en-US/_reference/gen_ai_hub.html)
- [Orchestration Service V2 examples](https://help.sap.com/doc/generative-ai-hub-sdk/CLOUD/en-US/_reference/orchestration-service2.html)
- [Streaming examples](https://help.sap.com/doc/generative-ai-hub-sdk/CLOUD/en-US/_reference/streaming.html)
- [Python SDK examples index](https://help.sap.com/doc/generative-ai-hub-sdk/CLOUD/en-US/examples.html)
- [Orchestration V2 API reference](https://help.sap.com/doc/generative-ai-hub-sdk/CLOUD/en-US/_api_doc/gen_ai_hub.orchestration_v2.html)
- [SAP AI Core Python SDK](https://pypi.org/project/sap-ai-sdk-core/)
- [SAP AI Core proxy repository conventions](../../README.md)

### Version note

This guide targets `sap-ai-sdk-gen 7.2.0`, checked against the installed package in this repository on 2026-08-30. Model availability, deployment behavior, provider parameters, cache support, and Orchestration module schemas can change. Re-run focused examples against the target tenant after every SDK upgrade.
