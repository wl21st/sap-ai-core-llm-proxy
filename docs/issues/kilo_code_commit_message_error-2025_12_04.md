---
name: Kilo Code Commit Message Generation Error
about: JSONDecodeError when generating commit messages via Kilo Code
title: '[BUG] JSONDecodeError in handle_non_streaming_request during commit message generation'
labels: bug, kilo-code, json-parsing
assignees: ''

---

## Bug Description

When using Kilo Code's "generate commit message" feature, the proxy server encounters a `JSONDecodeError` when attempting to parse the response from the Claude API. The error occurs in the [`handle_non_streaming_request()`](proxy_server.py:2334) function at line 2359.

## Error Details

```
2025-12-04 21:44:33,982 - INFO - Non-streaming request succeeded for model 'sonnet-4.5' using subAccount 'subAccount1'
2025-12-04 21:44:33,982 - ERROR - Error in non-streaming request: Expecting value: line 1 column 1 (char 0)
Traceback (most recent call last):
  File "requests/models.py", line 976, in json
  File "json/__init__.py", line 346, in loads
  File "json/decoder.py", line 345, in decode
  File "json/decoder.py", line 363, in raw_decode
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "proxy_server.py", line 2359, in handle_non_streaming_request
    final_response = convert_claude_to_openai(response.json(), model)
                                              ~~~~~~~~~~~~~^^
  File "requests/models.py", line 980, in json
requests.exceptions.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

## Root Cause Analysis

The error occurs at line 2359 in [`handle_non_streaming_request()`](proxy_server.py:2359):

```python
final_response = convert_claude_to_openai(response.json(), model)
```

The issue is that:

1. The request to the backend API succeeds (status code indicates success)
2. However, the response body is empty or contains invalid JSON
3. When attempting to call [`response.json()`](proxy_server.py:2359), it fails because there's no valid JSON to parse

## Context

- **Model**: `sonnet-4.5`
- **SubAccount**: `subAccount1`
- **Request Type**: Non-streaming
- **Use Case**: Kilo Code commit message generation
- **Endpoint**: `/v1/chat/completions`

## Request Payload

The request includes a large prompt for conventional commit message generation with git diff context:

```json
{
  "model": "sonnet-4.5",
  "messages": [
    {
      "role": "user",
      "content": "# Conventional Commit Message Generator\n..."
    }
  ]
}
```

## Proposed Solutions

### Solution 1: Add Response Body Validation (Recommended)

Add validation before attempting to parse JSON in [`handle_non_streaming_request()`](proxy_server.py:2334):

```python
def handle_non_streaming_request(url, headers, payload, model, subaccount_name):
    try:
        # Make request to backend API
        response = requests.post(url, headers=headers, json=payload, timeout=600)
        response.raise_for_status()
        logging.info(f"Non-streaming request succeeded for model '{model}' using subAccount '{subaccount_name}'")

        # Validate response has content before parsing
        if not response.content:
            logging.error("Empty response body received from backend API")
            return jsonify({"error": "Empty response from backend API"}), 500

        # Log raw response for debugging
        logging.debug(f"Raw response content: {response.text[:500]}...")

        # Attempt to parse JSON
        try:
            response_json = response.json()
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON response: {e}")
            logging.error(f"Response content: {response.text}")
            return jsonify({
                "error": "Invalid JSON response from backend API",
                "details": str(e),
                "response_preview": response.text[:200]
            }), 500

        # Process response based on model type
        if is_claude_model(model):
            final_response = convert_claude_to_openai(response_json, model)
        elif is_gemini_model(model):
            final_response = convert_gemini_to_openai(response_json, model)
        else:
            final_response = response_json

        # ... rest of the function
```

### Solution 2: Investigate Backend API Response

The backend API might be returning:

- An empty response body
- A non-JSON response (e.g., plain text error message)
- A response with incorrect `Content-Type` header

**Action Items:**

1. Add logging to capture the raw response body before parsing
2. Check the `Content-Type` header of the response
3. Verify the backend API is returning valid JSON for commit message generation requests

### Solution 3: Add Retry Logic

Implement retry logic for failed JSON parsing:

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def make_api_request(url, headers, payload):
    response = requests.post(url, headers=headers, json=payload, timeout=600)
    response.raise_for_status()
    
    if not response.content:
        raise ValueError("Empty response body")
    
    return response.json()
```

## Steps to Reproduce

1. Use Kilo Code extension in VS Code
2. Stage some changes in git
3. Trigger "Generate Commit Message" feature
4. Observe the error in proxy server logs

## Expected Behavior

The proxy server should:

1. Successfully receive and parse the response from the backend API
2. Convert the Claude response to OpenAI format
3. Return a valid commit message to Kilo Code

## Actual Behavior

The proxy server:

1. Receives a response with status code indicating success
2. Attempts to parse an empty or invalid JSON response
3. Throws `JSONDecodeError` and returns error to client

## Environment

- **OS**: macOS
- **Python Version**: 3.x
- **Proxy Server**: sap-ai-core-llm-proxy
- **Backend**: SAP AI Core with Claude models

## Additional Context

This error specifically occurs during Kilo Code's commit message generation, which sends a large prompt with git diff context. The request payload includes:

- System instructions for conventional commit message generation
- Full git diff of unstaged changes
- Change summary and repository context

The large payload size might be causing issues with the backend API response handling.

## Related Code Sections

- [`handle_non_streaming_request()`](proxy_server.py:2334) - Main error location
- [`convert_claude_to_openai()`](proxy_server.py:718) - Response conversion function
- [`proxy_openai_stream()`](proxy_server.py:1881) - Main endpoint handler

## Priority

**High** - This breaks a core feature of the Kilo Code integration and affects developer workflow.
