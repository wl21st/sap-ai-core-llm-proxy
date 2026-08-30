# SAP AI Core Generative AI Hub API Reference

This document provides endpoint specifications, authentication requirements, and request/response payload examples for consuming models through SAP AI Core's Generative AI Hub.

---

## 1. Authentication & Common Headers

All upstream SAP AI Core deployment endpoints require OAuth 2.0 bearer authentication:

| Header | Value | Description |
|---|---|---|
| `Authorization` | `Bearer <SAP_AI_CORE_OAUTH_TOKEN>` | OAuth token obtained from SAP AI Core auth service |
| `AI-Resource-Group` | `<Resource Group ID>` | Target resource group (e.g. `default`) |
| `Content-Type` | `application/json` | JSON payload format |

---

## 2. OpenAI Deployments (GPT-4o, GPT-4.1, Embeddings)

### Chat Completions
- **Endpoint**: `$DEPLOYMENT_URL/chat/completions?api-version=2023-05-15`
- **Request Payload**:
  ```json
  {
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "Hello!"}
    ],
    "max_tokens": 1024,
    "temperature": 0.7,
    "stream": false
  }
  ```

### Embeddings
- **Endpoint**: `$DEPLOYMENT_URL/embeddings?api-version=2023-05-15`
- **Request Payload**:
  ```json
  {
    "input": ["Sample text to embed"],
    "model": "text-embedding-3-small"
  }
  ```

---

## 3. AWS Bedrock Deployments (Claude 3.5, 3.7, 4.x)

### Claude 3.7 & 4.x (Bedrock Converse API)
- **Endpoint**: `$DEPLOYMENT_URL/converse` (or `/converse-stream`)
- **Request Payload**:
  ```json
  {
    "messages": [
      {
        "role": "user",
        "content": [{"text": "Hello, Claude"}]
      }
    ],
    "system": [{"text": "You are an expert engineer."}],
    "inferenceConfig": {
      "maxTokens": 4096,
      "temperature": 0.5
    },
    "additionalModelRequestFields": {
      "thinking": {
        "type": "enabled",
        "budget_tokens": 2048
      }
    }
  }
  ```

### Claude 3.5 & Older (Bedrock Invoke API)
- **Endpoint**: `$DEPLOYMENT_URL/invoke` (or `/invoke-with-response-stream`)
- **Request Payload**:
  ```json
  {
    "anthropic_version": "bedrock-2023-05-31",
    "messages": [
      {"role": "user", "content": [{"text": "Hello"}]}
    ],
    "system": "You are an expert engineer.",
    "max_tokens": 4096
  }
  ```

---

## 4. Google Vertex AI Deployments (Gemini 1.5 & 2.5)

### Content Generation
- **Endpoint**: `$DEPLOYMENT_URL/models/{model}:generateContent` (or `:streamGenerateContent`)
- **Request Payload**:
  ```json
  {
    "contents": [
      {
        "role": "user",
        "parts": [{"text": "Hello, Gemini"}]
      }
    ],
    "system_instruction": {
      "parts": [{"text": "You are a helpful assistant."}]
    },
    "generation_config": {
      "maxOutputTokens": 2048,
      "temperature": 0.7
    }
  }
  ```
