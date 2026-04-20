# SAP Orchestration API Model Access & Deployment Changes

**Session ID:** ses_25b9eef91ffeMQ47Hmkeoc3gxV
**Created:** 4/18/2026, 11:15:17 PM
**Updated:** 4/18/2026, 11:20:10 PM

---

## User

how to use sap orchestration api to know what the model available and access the model,    
  orchestration api will no longer have deployment.  investigate and find out    

---

## Assistant (Code · anthropic--claude-4.6-sonnet · 108.4s)

**Tool: task**

**Input:**
```json
{
  "description": "Investigate SAP orchestration API",
  "subagent_type": "explore",
  "prompt": "Investigate the SAP AI Core orchestration API in this codebase. I need to understand:\n1. How the current proxy handles SAP AI Core APIs\n2. Any existing code related to \"orchestration\" endpoints\n3. How deployments are currently discovered/listed\n4. Any references to model listing or available models\n\nLook through these key files:\n- proxy_server.py\n- proxy_helpers.py\n- config/config_parser.py\n- auth/token_manager.py\n- Any test files that mention orchestration\n\nReturn:\n- Relevant code snippets with file paths and line numbers\n- How deployments are currently used\n- Any existing orchestration-related code\n- The overall architecture for how models are accessed"
}
```

**Output:**
```
task_id: ses_25b9ecf61ffenGNjMtaLf1heGD (for resuming to continue this task if needed)

<task_result>
Here is a comprehensive breakdown of the SAP AI Core orchestration API investigation:

---

## 1. Overall Architecture — How the Proxy Handles SAP AI Core APIs

The app is **FastAPI** (migrated from Flask). Entry point: `main.py:create_app()`.

**Request flow for `/v1/chat/completions`:**
1. `routers/chat.py:107` — receives OpenAI-format request
2. `load_balancer.resolve_model_name()` — resolves model name with fallbacks
3. `handlers/model_handlers.py` — dispatches to `handle_claude_request`, `handle_gemini_request`, or `handle_default_request`
4. `load_balance_url(model, proxy_config)` → returns `(deployment_url, subaccount_name, resource_group, model)`
5. Payload converted to backend format (Claude `/converse` or `/invoke`, Gemini `/generateContent`, OpenAI `/chat/completions`)
6. Token fetched via `ProxyGlobalContext.get_token_manager(subaccount_name).get_token()`
7. Headers sent: `AI-Resource-Group`, `Authorization: Bearer <token>`, `AI-Tenant-Id`

---

## 2. All Flask/FastAPI Routes

| Method | Path | File | Auth |
|--------|------|------|------|
| `POST` | `/v1/chat/completions` | `routers/chat.py:106` | ✅ |
| `POST` | `/v1/messages` | `routers/messages.py:86` | ✅ |
| `POST` | `/v1/embeddings` | `routers/embeddings.py` | ✅ |
| `GET/OPTIONS` | `/v1/models` | `routers/models.py:17` | ✅ |
| `GET` | `/health` | `routers/status.py:16` | ❌ |
| `GET` | `/stats` | `routers/status.py:27` | ❌ |
| `GET` | `/info` | `routers/status.py:58` | ❌ |

---

## 3. Existing Orchestration-Related Code

**None exists in the codebase.** The only reference is:
- `.git/FETCH_HEAD:8` — a remote branch named `feat/sap-ai-orchestration-model-discovery` (not yet merged)
- `openspec/changes/refactor-extract-routing-module/design.md:101` — uses "orchestration" in a generic architectural context only

There is **zero code** targeting the SAP AI Core `/lm/orchestration` endpoint.

---

## 4. Deployment Discovery — How It Works

Two modes, both resolved at startup in `config/config_parser.py:_build_mapping_for_subaccount()` (line 592):

**Auto-Discovery** (`_auto_discover_deployments`, line 318):
- Calls `fetch_all_deployments(service_key, resource_group)` in `utils/sdk_utils.py:277`
- Uses `AIAPIV2Client` targeting `{AI_API_URL}/v2/lm`
- Calls `client.deployment.query()` — queries all running deployments
- Extracts model name from `deployment.details["resources"]["backend_details"]["model"]["name"]`
- Results are **disk-cached for 7 days** at `~/.sap-ai-proxy/cache/deployments`

**Configured Deployment IDs** (`_resolve_deployment_ids`, line 429):
- Takes `deployment_ids: dict[str, list[str]]` from config JSON
- Uses `AICoreV2Client.deployment.get(deployment_id)` → fetches the deployment URL
- Validates model/deployment consistency via `Detector.validate_model_mapping()`

**URL format:** `https://{host}/v2/inference/deployments/{deployment_id}` (extracted at `utils/sdk_utils.py:167`)

---

## 5. Model Listing (`GET /v1/models`)

`routers/models.py:27`:
```python
for model_name in proxy_config.model_to_subaccounts.keys():
    models.append({"id": model_name, "object": "model", "created": timestamp, "owned_by": "sap-ai-core"})
```
Source of truth = all models discovered/configured across all subaccounts at startup time.

---

## 6. Config Structure

**`ServiceKey`** (`config/config_models.py:39`):
```python
client_id: str
client_secret: str
auth_url: str           # OAuth token endpoint base
identity_zone_id: str
api_url: str            # AI_API_URL (e.g. https://api.ai.*.cfapps.sap.hana.ondemand.com)
```

**`SubAccountConfig`** (`config/config_models.py:59`):
```python
name: str
resource_group: str
service_key_json: str
model_to_deployment_urls: dict[str, list[str]]   # model_name -> [url1, url2]
model_to_deployment_ids: dict[str, list[str]]    # model_name -> [dep_id1, dep_id2]
service_key: ServiceKey
token_info: TokenInfo
```

**`ProxyConfig`** (`config/config_models.py:72`):
```python
subaccounts: dict[str, SubAccountConfig]
secret_authentication_tokens: list[str]
port: int = 3001
host: str = "127.0.0.1"
model_filters: Optional[ModelFilters]
model_to_subaccounts: dict[str, list[str]]       # model_name -> [subaccount_name1, ...]
ca_cert_bundle: Optional[str]
```

---

## 7. Token Fetch and Caching (`auth/token_manager.py`)

- `get_token()` (line 49): thread-safe; returns cached token if valid, else calls `_fetch_new_token()`
- `_fetch_new_token()` (line 89): POSTs to `{auth_url}/oauth/token?grant_type=client_credentials` with base64-encoded `client_id:client_secret`
- Cache expiry: `time.time() + expires_in - 300` (5-minute buffer before actual expiry)
- Thread safety: `threading.Lock` (line 47)
- `invalidate_token()` (line 76): resets token for forced refresh on 401/403

---

## 8. SAP AI Core REST Calls Made

| Call | Location | Endpoint |
|------|----------|----------|
| List all deployments | `utils/sdk_utils.py:335` | `{AI_API_URL}/v2/lm/deployments` |
| Get single deployment | `utils/sdk_utils.py:234` | `{AI_API_URL}/v2/lm/deployments/{id}` |
| OAuth token | `auth/token_manager.py:128` | `{auth_url}/oauth/token` |
| Model inference | `routers/chat.py` | `{deployment_url}/{endpoint_path}` |

The SDK base URL is `{AI_API_URL}/v2/lm` (`utils/sdk_utils.py:92,147`). The orchestration endpoint would be at `{AI_API_URL}/v2/inference/deployments/{orchestration_deployment_id}/completion`.
</task_result>
```

---

## Assistant (Code · anthropic--claude-4.6-sonnet · 5.4s)

Now let me research the SAP AI Core Orchestration API (the new "deployment-less" API) from the official documentation:

**Tool: webfetch**

**Input:**
```json
{
  "url": "https://help.sap.com/docs/sap-ai-core/sap-ai-core-service-guide/orchestration",
  "format": "markdown"
}
```

**Output:**
```
   SAP Help Portal | SAP Online Help
```

**Tool: webfetch**

**Input:**
```json
{
  "url": "https://api.sap.com/api/AI_CORE_API/overview",
  "format": "markdown"
}
```

---

## Assistant (Code · anthropic--claude-4.6-sonnet · 4.3s)

**Tool: webfetch**

**Input:**
```json
{
  "url": "https://help.sap.com/docs/sap-ai-core/sap-ai-core-service-guide/orchestration-service",
  "format": "markdown"
}
```

**Output:**
```
   SAP Help Portal | SAP Online Help
```

**Tool: webfetch**

**Input:**
```json
{
  "url": "https://developers.sap.com/tutorials/ai-core-orchestration.html",
  "format": "markdown"
}
```

**Error:**
```
Error: Request failed with status code: 404
```

---

## Assistant (Code · anthropic--claude-4.6-sonnet · 3.6s)

**Tool: webfetch**

**Input:**
```json
{
  "url": "https://help.sap.com/docs/sap-ai-core/sap-ai-core-service-guide/gen-ai-hub-orchestration",
  "format": "markdown"
}
```

**Output:**
```
   SAP Help Portal | SAP Online Help
```

**Tool: webfetch**

**Input:**
```json
{
  "url": "https://pypi.org/project/generative-ai-hub-sdk/",
  "format": "markdown"
}
```

**Output:**
```
     generative-ai-hub-sdk · PyPI    

             [Skip to main content](#content) Switch to mobile version

Warning Some features may not work without JavaScript. Please try enabling it if you encounter problems.

[![PyPI](/static/images/logo-small.8998e9d1.svg)](/)

Search PyPI  Search

-   [Help](/help/)
-   [Docs](https://docs.pypi.org/)
-   [Sponsors](/sponsors/)
-   [Log in](/account/login/?next=https%3A%2F%2Fpypi.org%2Fproject%2Fgenerative-ai-hub-sdk%2F)
-   [Register](/account/register/)

Menu

-   [Help](/help/)
-   [Docs](https://docs.pypi.org/)
-   [Sponsors](/sponsors/)
-   [Log in](/account/login/?next=https%3A%2F%2Fpypi.org%2Fproject%2Fgenerative-ai-hub-sdk%2F)
-   [Register](/account/register/)

Search PyPI  Search

# generative-ai-hub-sdk 4.12.4

pip install generative-ai-hub-sdk Copy PIP instructions

[Latest version](/project/generative-ai-hub-sdk/)

Released: May 14, 2025

\[DEPRECATED\] generative AI hub SDK

### Navigation

-   [Project description](#description)
-   [Release history](#history)
-   [Download files](#files)

### Verified details

*These details have been [verified by PyPI](https://docs.pypi.org/project_metadata/#verified-details)*

###### Maintainers

 [![Avatar for SAP from gravatar.com](https://pypi-camo.freetls.fastly.net/c38f8c6db62becdde8ef9a2457f54396ec4e54ac/68747470733a2f2f7365637572652e67726176617461722e636f6d2f6176617461722f34303265633562623533653136313335383431303563663263396630373339633f73697a653d3530 "Avatar for SAP from gravatar.com")SAP](/user/SAP/)

### Unverified details

*These details have **not** been verified by PyPI*

###### Project links

-   [Homepage](https://www.sap.com/)
-   [Download](https://pypi.python.org/pypi/generative-ai-hub-sdk)

###### Meta

-   **License:** Other/Proprietary License (SAP DEVELOPER LICENSE AGREEMENT)
-   **Author:** SAP SE
-   Tags SAP generative AI hub SDK , SAP AI Core API , SAP AI Core
-   **Requires:** Python >=3.9
-   **Provides-Extra:** `all` , `amazon` , `google` , `langchain`

###### Classifiers

-   **Development Status**
    -   [7 - Inactive](/search/?c=Development+Status+%3A%3A+7+-+Inactive)
-   **Intended Audience**
    -   [Developers](/search/?c=Intended+Audience+%3A%3A+Developers)
-   **License**
    -   [Other/Proprietary License](/search/?c=License+%3A%3A+Other%2FProprietary+License)
-   **Operating System**
    -   [MacOS :: MacOS X](/search/?c=Operating+System+%3A%3A+MacOS+%3A%3A+MacOS+X)
    -   [Microsoft :: Windows :: Windows 7](/search/?c=Operating+System+%3A%3A+Microsoft+%3A%3A+Windows+%3A%3A+Windows+7)
    -   [Microsoft :: Windows :: Windows 8](/search/?c=Operating+System+%3A%3A+Microsoft+%3A%3A+Windows+%3A%3A+Windows+8)
    -   [Microsoft :: Windows :: Windows 8.1](/search/?c=Operating+System+%3A%3A+Microsoft+%3A%3A+Windows+%3A%3A+Windows+8.1)
    -   [Microsoft :: Windows :: Windows 10](/search/?c=Operating+System+%3A%3A+Microsoft+%3A%3A+Windows+%3A%3A+Windows+10)
    -   [Microsoft :: Windows :: Windows Server 2008](/search/?c=Operating+System+%3A%3A+Microsoft+%3A%3A+Windows+%3A%3A+Windows+Server+2008)
    -   [POSIX :: Linux](/search/?c=Operating+System+%3A%3A+POSIX+%3A%3A+Linux)
-   **Programming Language**
    -   [Python](/search/?c=Programming+Language+%3A%3A+Python)
    -   [Python :: 3](/search/?c=Programming+Language+%3A%3A+Python+%3A%3A+3)
    -   [Python :: 3.9](/search/?c=Programming+Language+%3A%3A+Python+%3A%3A+3.9)
    -   [Python :: 3.10](/search/?c=Programming+Language+%3A%3A+Python+%3A%3A+3.10)
    -   [Python :: 3.11](/search/?c=Programming+Language+%3A%3A+Python+%3A%3A+3.11)
    -   [Python :: 3.12](/search/?c=Programming+Language+%3A%3A+Python+%3A%3A+3.12)
-   **Topic**
    -   [Software Development :: Libraries :: Python Modules](/search/?c=Topic+%3A%3A+Software+Development+%3A%3A+Libraries+%3A%3A+Python+Modules)

[Report project as malware](https://pypi.org/project/generative-ai-hub-sdk/submit-malware-report/)

-   [Project description](#description)
-   [Project details](#data)
-   [Release history](#history)
-   [Download files](#files)

This project has been archived.

The maintainers of this project have marked this project as archived. No new releases are expected.

## Project description

# \[DEPRECATED\] SAP generative AI hub SDK

**This package is no longer maintained.**

Please use [sap-ai-sdk-gen](https://pypi.org/project/sap-ai-sdk-gen/) instead.

---

With this SDK you can leverage the power of generative models available in the generative AI Hub of SAP AI Core. The generative AI Hub SDK provides model access by wrapping the native SDKs of the model providers (OpenAI, Amazon, Google), through langchain, or through the orchestration service.

## Installation

To install this SDK, use the following pip command, which includes support for all models including langchain support:

```
pip install "generative-ai-hub-sdk[all]"
```

The default installation only includes OpenAI models (without langchain support):

```
pip install generative-ai-hub-sdk
```

You can install a subset of the extra libraries (without langchain support) by specifying them in square brackets:

```
pip install "generative-ai-hub-sdk[google, amazon]"
```

## Configuration, Usage

Please refer to the official documentation hosted on [help.sap.com](https://help.sap.com/doc/generative-ai-hub-sdk/CLOUD/en-US/index.html) for details on how to configure and use the generative AI hub SDK.

## Project details

### Verified details

*These details have been [verified by PyPI](https://docs.pypi.org/project_metadata/#verified-details)*

###### Maintainers

 [![Avatar for SAP from gravatar.com](https://pypi-camo.freetls.fastly.net/c38f8c6db62becdde8ef9a2457f54396ec4e54ac/68747470733a2f2f7365637572652e67726176617461722e636f6d2f6176617461722f34303265633562623533653136313335383431303563663263396630373339633f73697a653d3530 "Avatar for SAP from gravatar.com")SAP](/user/SAP/)

### Unverified details

*These details have **not** been verified by PyPI*

###### Project links

-   [Homepage](https://www.sap.com/)
-   [Download](https://pypi.python.org/pypi/generative-ai-hub-sdk)

###### Meta

-   **License:** Other/Proprietary License (SAP DEVELOPER LICENSE AGREEMENT)
-   **Author:** SAP SE
-   Tags SAP generative AI hub SDK , SAP AI Core API , SAP AI Core
-   **Requires:** Python >=3.9
-   **Provides-Extra:** `all` , `amazon` , `google` , `langchain`

###### Classifiers

-   **Development Status**
    -   [7 - Inactive](/search/?c=Development+Status+%3A%3A+7+-+Inactive)
-   **Intended Audience**
    -   [Developers](/search/?c=Intended+Audience+%3A%3A+Developers)
-   **License**
    -   [Other/Proprietary License](/search/?c=License+%3A%3A+Other%2FProprietary+License)
-   **Operating System**
    -   [MacOS :: MacOS X](/search/?c=Operating+System+%3A%3A+MacOS+%3A%3A+MacOS+X)
    -   [Microsoft :: Windows :: Windows 7](/search/?c=Operating+System+%3A%3A+Microsoft+%3A%3A+Windows+%3A%3A+Windows+7)
    -   [Microsoft :: Windows :: Windows 8](/search/?c=Operating+System+%3A%3A+Microsoft+%3A%3A+Windows+%3A%3A+Windows+8)
    -   [Microsoft :: Windows :: Windows 8.1](/search/?c=Operating+System+%3A%3A+Microsoft+%3A%3A+Windows+%3A%3A+Windows+8.1)
    -   [Microsoft :: Windows :: Windows 10](/search/?c=Operating+System+%3A%3A+Microsoft+%3A%3A+Windows+%3A%3A+Windows+10)
    -   [Microsoft :: Windows :: Windows Server 2008](/search/?c=Operating+System+%3A%3A+Microsoft+%3A%3A+Windows+%3A%3A+Windows+Server+2008)
    -   [POSIX :: Linux](/search/?c=Operating+System+%3A%3A+POSIX+%3A%3A+Linux)
-   **Programming Language**
    -   [Python](/search/?c=Programming+Language+%3A%3A+Python)
    -   [Python :: 3](/search/?c=Programming+Language+%3A%3A+Python+%3A%3A+3)
    -   [Python :: 3.9](/search/?c=Programming+Language+%3A%3A+Python+%3A%3A+3.9)
    -   [Python :: 3.10](/search/?c=Programming+Language+%3A%3A+Python+%3A%3A+3.10)
    -   [Python :: 3.11](/search/?c=Programming+Language+%3A%3A+Python+%3A%3A+3.11)
    -   [Python :: 3.12](/search/?c=Programming+Language+%3A%3A+Python+%3A%3A+3.12)
-   **Topic**
    -   [Software Development :: Libraries :: Python Modules](/search/?c=Topic+%3A%3A+Software+Development+%3A%3A+Libraries+%3A%3A+Python+Modules)

  

## Release history [Release notifications](/help/#project-release-notifications) | [RSS feed](/rss/project/generative-ai-hub-sdk/releases.xml)

This version

![](https://pypi.org/static/images/blue-cube.572a5bfb.svg)

[

4.12.4

May 14, 2025

](/project/generative-ai-hub-sdk/4.12.4/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

4.10.2

Apr 4, 2025

](/project/generative-ai-hub-sdk/4.10.2/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

4.4.3

Feb 27, 2025

](/project/generative-ai-hub-sdk/4.4.3/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

4.3.1

Feb 5, 2025

](/project/generative-ai-hub-sdk/4.3.1/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

4.1.1

Dec 16, 2024

](/project/generative-ai-hub-sdk/4.1.1/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

4.0.0

Dec 4, 2024

](/project/generative-ai-hub-sdk/4.0.0/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

3.8.0

Nov 4, 2024

](/project/generative-ai-hub-sdk/3.8.0/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

3.2.6

Oct 7, 2024

](/project/generative-ai-hub-sdk/3.2.6/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

3.1.1

Sep 16, 2024

](/project/generative-ai-hub-sdk/3.1.1/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

3.1.0

Sep 5, 2024

](/project/generative-ai-hub-sdk/3.1.0/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

2.1.1

Aug 20, 2024

](/project/generative-ai-hub-sdk/2.1.1/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

1.11.1

Jul 10, 2024

](/project/generative-ai-hub-sdk/1.11.1/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

1.8.0

Jun 12, 2024

](/project/generative-ai-hub-sdk/1.8.0/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

1.2.2

Feb 7, 2024

](/project/generative-ai-hub-sdk/1.2.2/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

1.2.0

Feb 2, 2024

](/project/generative-ai-hub-sdk/1.2.0/)

## Download files

Download the file for your platform. If you're not sure which to choose, learn more about [installing packages](https://packaging.python.org/tutorials/installing-packages/ "External link").

### Source Distributions

No source distribution files available for this release.See tutorial on [generating distribution archives](https://packaging.python.org/tutorials/packaging-projects/#generating-distribution-archives "External link").

### Built Distribution

Filter files by name, interpreter, ABI, and platform.

If you're not sure about the file name format, learn more about [wheel file names](https://packaging.python.org/en/latest/specifications/binary-distribution-format/ "External link").

The dropdown lists show the available interpreters, ABIs, and platforms.

Enable javascript to be able to filter the list of wheel files.

Copy a direct link to the current filters [](https://pypi.org/project/generative-ai-hub-sdk/#files)Copy

File name 

Interpreter Interpreter py3

ABI ABI none

Platform Platform any

[generative\_ai\_hub\_sdk-4.12.4-py3-none-any.whl](https://files.pythonhosted.org/packages/05/91/8ab38256d54c5bd1eb7b73a108d52dc5b184ff5b951be40bbe4ebf5c7fef/generative_ai_hub_sdk-4.12.4-py3-none-any.whl) (613.6 kB [view details](#generative_ai_hub_sdk-4.12.4-py3-none-any.whl))

Uploaded May 14, 2025 `Python 3`

## File details

Details for the file `generative_ai_hub_sdk-4.12.4-py3-none-any.whl`.

### File metadata

-   Download URL: [generative\_ai\_hub\_sdk-4.12.4-py3-none-any.whl](https://files.pythonhosted.org/packages/05/91/8ab38256d54c5bd1eb7b73a108d52dc5b184ff5b951be40bbe4ebf5c7fef/generative_ai_hub_sdk-4.12.4-py3-none-any.whl)
-   Upload date: May 14, 2025
-   Size: 613.6 kB
-   Tags: Python 3
-   Uploaded using Trusted Publishing? No
-   Uploaded via: twine/6.1.0 CPython/3.12.1

### File hashes

Hashes for generative\_ai\_hub\_sdk-4.12.4-py3-none-any.whl

Algorithm

Hash digest

SHA256

`4ca9bfb66fc637106167b1bdf81257604c6371294047f346604e8b81ce683608`

Copy

MD5

`7874bd3b85b31a489ad92ed4ba343b59`

Copy

BLAKE2b-256

`05918ab38256d54c5bd1eb7b73a108d52dc5b184ff5b951be40bbe4ebf5c7fef`

Copy

[See more details on using hashes here.](https://pip.pypa.io/en/stable/topics/secure-installs/#hash-checking-mode "External link")

![](/static/images/white-cube.2351a86c.svg)

## Help

-   [Installing packages](https://packaging.python.org/tutorials/installing-packages/ "External link")
-   [Uploading packages](https://packaging.python.org/tutorials/packaging-projects/ "External link")
-   [User guide](https://packaging.python.org/ "External link")
-   [Project name retention](https://www.python.org/dev/peps/pep-0541/ "External link")
-   [FAQs](/help/)

## About PyPI

-   [PyPI Blog](https://blog.pypi.org "External link")
-   [Infrastructure dashboard](https://dtdg.co/pypi "External link")
-   [Statistics](/stats/)
-   [Logos & trademarks](/trademarks/)
-   [Our sponsors](/sponsors/)

## Contributing to PyPI

-   [Bugs and feedback](/help/#feedback)
-   [Contribute on GitHub](https://github.com/pypi/warehouse "External link")
-   [Translate PyPI](https://hosted.weblate.org/projects/pypa/warehouse/ "External link")
-   [Sponsor PyPI](/sponsors/)
-   [Development credits](https://github.com/pypi/warehouse/graphs/contributors "External link")

## Using PyPI

-   [Terms of Service](https://policies.python.org/pypi.org/Terms-of-Service/ "External link")
-   [Report security issue](/security/)
-   [Code of conduct](https://policies.python.org/python.org/code-of-conduct/ "External link")
-   [Privacy Notice](https://policies.python.org/pypi.org/Privacy-Notice/ "External link")
-   [Acceptable Use Policy](https://policies.python.org/pypi.org/Acceptable-Use-Policy/ "External link")

---

Status: [all systems operational](https://status.python.org/ "External link")

Developed and maintained by the Python community, for the Python community.  
[Donate today!](https://donate.pypi.org)

"PyPI", "Python Package Index", and the blocks logos are registered [trademarks](/trademarks/) of the [Python Software Foundation](https://www.python.org/psf-landing).  

© 2026 [Python Software Foundation](https://www.python.org/psf-landing/ "External link")  
[Site map](/sitemap/)

Switch to desktop version

-   English
-   español
-   français
-   日本語
-   português (Brasil)
-   українська
-   Ελληνικά
-   Deutsch
-   中文 (简体)
-   中文 (繁體)
-   русский
-   עברית
-   Esperanto
-   한국어

Supported by

 [![](https://pypi-camo.freetls.fastly.net/ed7074cadad1a06f56bc520ad9bd3e00d0704c5b/68747470733a2f2f73746f726167652e676f6f676c65617069732e636f6d2f707970692d6173736574732f73706f6e736f726c6f676f732f6177732d77686974652d6c6f676f2d7443615473387a432e706e67) AWS Cloud computing and Security Sponsor](https://aws.amazon.com/)[![](https://pypi-camo.freetls.fastly.net/8855f7c063a3bdb5b0ce8d91bfc50cf851cc5c51/68747470733a2f2f73746f726167652e676f6f676c65617069732e636f6d2f707970692d6173736574732f73706f6e736f726c6f676f732f64617461646f672d77686974652d6c6f676f2d6668644c4e666c6f2e706e67) Datadog Monitoring ](https://www.datadoghq.com/)[![](https://pypi-camo.freetls.fastly.net/60f709d24f3e4d469f9adc77c65e2f5291a3d165/68747470733a2f2f73746f726167652e676f6f676c65617069732e636f6d2f707970692d6173736574732f73706f6e736f726c6f676f732f6465706f742d77686974652d6c6f676f2d7038506f476831302e706e67) Depot Continuous Integration ](https://depot.dev)[![](https://pypi-camo.freetls.fastly.net/df6fe8829cbff2d7f668d98571df1fd011f36192/68747470733a2f2f73746f726167652e676f6f676c65617069732e636f6d2f707970692d6173736574732f73706f6e736f726c6f676f732f666173746c792d77686974652d6c6f676f2d65684d3077735f6f2e706e67) Fastly CDN ](https://www.fastly.com/)[![](https://pypi-camo.freetls.fastly.net/420cc8cf360bac879e24c923b2f50ba7d1314fb0/68747470733a2f2f73746f726167652e676f6f676c65617069732e636f6d2f707970692d6173736574732f73706f6e736f726c6f676f732f676f6f676c652d77686974652d6c6f676f2d616734424e3774332e706e67) Google Download Analytics ](https://careers.google.com/)[![](https://pypi-camo.freetls.fastly.net/d01053c02f3a626b73ffcb06b96367fdbbf9e230/68747470733a2f2f73746f726167652e676f6f676c65617069732e636f6d2f707970692d6173736574732f73706f6e736f726c6f676f732f70696e67646f6d2d77686974652d6c6f676f2d67355831547546362e706e67) Pingdom Monitoring ](https://www.pingdom.com/)[![](https://pypi-camo.freetls.fastly.net/67af7117035e2345bacb5a82e9aa8b5b3e70701d/68747470733a2f2f73746f726167652e676f6f676c65617069732e636f6d2f707970692d6173736574732f73706f6e736f726c6f676f732f73656e7472792d77686974652d6c6f676f2d4a2d6b64742d706e2e706e67) Sentry Error logging ](https://sentry.io/for/python/?utm_source=pypi&utm_medium=paid-community&utm_campaign=python-na-evergreen&utm_content=static-ad-pypi-sponsor-learnmore)[![](https://pypi-camo.freetls.fastly.net/b611884ff90435a0575dbab7d9b0d3e60f136466/68747470733a2f2f73746f726167652e676f6f676c65617069732e636f6d2f707970692d6173736574732f73706f6e736f726c6f676f732f737461747573706167652d77686974652d6c6f676f2d5467476c6a4a2d502e706e67) StatusPage Status page](https://statuspage.io)
```

---

## Assistant (Code · anthropic--claude-4.6-sonnet · 3.9s)

**Tool: webfetch**

**Input:**
```json
{
  "url": "https://pypi.org/project/sap-ai-sdk-gen/",
  "format": "markdown"
}
```

**Output:**
```
     sap-ai-sdk-gen · PyPI    

             [Skip to main content](#content) Switch to mobile version

Warning Some features may not work without JavaScript. Please try enabling it if you encounter problems.

[![PyPI](/static/images/logo-small.8998e9d1.svg)](/)

Search PyPI  Search

-   [Help](/help/)
-   [Docs](https://docs.pypi.org/)
-   [Sponsors](/sponsors/)
-   [Log in](/account/login/?next=https%3A%2F%2Fpypi.org%2Fproject%2Fsap-ai-sdk-gen%2F)
-   [Register](/account/register/)

Menu

-   [Help](/help/)
-   [Docs](https://docs.pypi.org/)
-   [Sponsors](/sponsors/)
-   [Log in](/account/login/?next=https%3A%2F%2Fpypi.org%2Fproject%2Fsap-ai-sdk-gen%2F)
-   [Register](/account/register/)

Search PyPI  Search

# sap-ai-sdk-gen 6.7.0

pip install sap-ai-sdk-gen Copy PIP instructions

[Latest version](/project/sap-ai-sdk-gen/)

Released: Mar 30, 2026

SAP Cloud SDK for AI (Python): generative AI SDK

### Navigation

-   [Project description](#description)
-   [Release history](#history)
-   [Download files](#files)

### Verified details

*These details have been [verified by PyPI](https://docs.pypi.org/project_metadata/#verified-details)*

###### Maintainers

 [![Avatar for SAP from gravatar.com](https://pypi-camo.freetls.fastly.net/c38f8c6db62becdde8ef9a2457f54396ec4e54ac/68747470733a2f2f7365637572652e67726176617461722e636f6d2f6176617461722f34303265633562623533653136313335383431303563663263396630373339633f73697a653d3530 "Avatar for SAP from gravatar.com")SAP](/user/SAP/)

### Unverified details

*These details have **not** been verified by PyPI*

###### Project links

-   [Homepage](https://www.sap.com/)
-   [Download](https://pypi.python.org/pypi/sap-ai-sdk-gen)

###### Meta

-   **License:** Other/Proprietary License (SAP DEVELOPER LICENSE AGREEMENT)
-   **Author:** SAP SE
-   Tags SAP AI Core , SAP generative AI SDK , SAP Generative AI Hub
-   **Requires:** Python >=3.9
-   **Provides-Extra:** `all` , `amazon` , `google`

###### Classifiers

-   **Development Status**
    -   [5 - Production/Stable](/search/?c=Development+Status+%3A%3A+5+-+Production%2FStable)
-   **Intended Audience**
    -   [Developers](/search/?c=Intended+Audience+%3A%3A+Developers)
-   **License**
    -   [Other/Proprietary License](/search/?c=License+%3A%3A+Other%2FProprietary+License)
-   **Operating System**
    -   [MacOS :: MacOS X](/search/?c=Operating+System+%3A%3A+MacOS+%3A%3A+MacOS+X)
    -   [Microsoft :: Windows :: Windows 7](/search/?c=Operating+System+%3A%3A+Microsoft+%3A%3A+Windows+%3A%3A+Windows+7)
    -   [Microsoft :: Windows :: Windows 8](/search/?c=Operating+System+%3A%3A+Microsoft+%3A%3A+Windows+%3A%3A+Windows+8)
    -   [Microsoft :: Windows :: Windows 8.1](/search/?c=Operating+System+%3A%3A+Microsoft+%3A%3A+Windows+%3A%3A+Windows+8.1)
    -   [Microsoft :: Windows :: Windows 10](/search/?c=Operating+System+%3A%3A+Microsoft+%3A%3A+Windows+%3A%3A+Windows+10)
    -   [Microsoft :: Windows :: Windows Server 2008](/search/?c=Operating+System+%3A%3A+Microsoft+%3A%3A+Windows+%3A%3A+Windows+Server+2008)
    -   [POSIX :: Linux](/search/?c=Operating+System+%3A%3A+POSIX+%3A%3A+Linux)
-   **Programming Language**
    -   [Python](/search/?c=Programming+Language+%3A%3A+Python)
    -   [Python :: 3](/search/?c=Programming+Language+%3A%3A+Python+%3A%3A+3)
    -   [Python :: 3.10](/search/?c=Programming+Language+%3A%3A+Python+%3A%3A+3.10)
    -   [Python :: 3.11](/search/?c=Programming+Language+%3A%3A+Python+%3A%3A+3.11)
    -   [Python :: 3.12](/search/?c=Programming+Language+%3A%3A+Python+%3A%3A+3.12)
    -   [Python :: 3.13](/search/?c=Programming+Language+%3A%3A+Python+%3A%3A+3.13)
    -   [Python :: 3.14](/search/?c=Programming+Language+%3A%3A+Python+%3A%3A+3.14)
-   **Topic**
    -   [Software Development :: Libraries :: Python Modules](/search/?c=Topic+%3A%3A+Software+Development+%3A%3A+Libraries+%3A%3A+Python+Modules)

[Report project as malware](https://pypi.org/project/sap-ai-sdk-gen/submit-malware-report/)

-   [Project description](#description)
-   [Project details](#data)
-   [Release history](#history)
-   [Download files](#files)

## Project description

# SAP Cloud SDK for AI (Python) - generative

With this SDK you can leverage the power of generative models available in the generative AI Hub of SAP AI Core. The SDK provides model access by wrapping the native SDKs of the model providers (OpenAI, Amazon, Google), through langchain, or through the orchestration service.

## Installation

To install this SDK, use the following pip command, which includes support for all models including langchain support:

```
pip install "sap-ai-sdk-gen[all]"
```

The default installation only includes OpenAI models (without langchain support):

```
pip install sap-ai-sdk-gen
```

You can install a subset of the extra libraries (without langchain support) by specifying them in square brackets:

```
pip install "sap-ai-sdk-gen[google, amazon]"
```

## Configuration, Usage

Please refer to the official documentation hosted on [help.sap.com](https://help.sap.com/doc/generative-ai-hub-sdk/CLOUD/en-US/index.html) for details on how to configure and use the SAP Cloud SDK for AI (Python).

## Project details

### Verified details

*These details have been [verified by PyPI](https://docs.pypi.org/project_metadata/#verified-details)*

###### Maintainers

 [![Avatar for SAP from gravatar.com](https://pypi-camo.freetls.fastly.net/c38f8c6db62becdde8ef9a2457f54396ec4e54ac/68747470733a2f2f7365637572652e67726176617461722e636f6d2f6176617461722f34303265633562623533653136313335383431303563663263396630373339633f73697a653d3530 "Avatar for SAP from gravatar.com")SAP](/user/SAP/)

### Unverified details

*These details have **not** been verified by PyPI*

###### Project links

-   [Homepage](https://www.sap.com/)
-   [Download](https://pypi.python.org/pypi/sap-ai-sdk-gen)

###### Meta

-   **License:** Other/Proprietary License (SAP DEVELOPER LICENSE AGREEMENT)
-   **Author:** SAP SE
-   Tags SAP AI Core , SAP generative AI SDK , SAP Generative AI Hub
-   **Requires:** Python >=3.9
-   **Provides-Extra:** `all` , `amazon` , `google`

###### Classifiers

-   **Development Status**
    -   [5 - Production/Stable](/search/?c=Development+Status+%3A%3A+5+-+Production%2FStable)
-   **Intended Audience**
    -   [Developers](/search/?c=Intended+Audience+%3A%3A+Developers)
-   **License**
    -   [Other/Proprietary License](/search/?c=License+%3A%3A+Other%2FProprietary+License)
-   **Operating System**
    -   [MacOS :: MacOS X](/search/?c=Operating+System+%3A%3A+MacOS+%3A%3A+MacOS+X)
    -   [Microsoft :: Windows :: Windows 7](/search/?c=Operating+System+%3A%3A+Microsoft+%3A%3A+Windows+%3A%3A+Windows+7)
    -   [Microsoft :: Windows :: Windows 8](/search/?c=Operating+System+%3A%3A+Microsoft+%3A%3A+Windows+%3A%3A+Windows+8)
    -   [Microsoft :: Windows :: Windows 8.1](/search/?c=Operating+System+%3A%3A+Microsoft+%3A%3A+Windows+%3A%3A+Windows+8.1)
    -   [Microsoft :: Windows :: Windows 10](/search/?c=Operating+System+%3A%3A+Microsoft+%3A%3A+Windows+%3A%3A+Windows+10)
    -   [Microsoft :: Windows :: Windows Server 2008](/search/?c=Operating+System+%3A%3A+Microsoft+%3A%3A+Windows+%3A%3A+Windows+Server+2008)
    -   [POSIX :: Linux](/search/?c=Operating+System+%3A%3A+POSIX+%3A%3A+Linux)
-   **Programming Language**
    -   [Python](/search/?c=Programming+Language+%3A%3A+Python)
    -   [Python :: 3](/search/?c=Programming+Language+%3A%3A+Python+%3A%3A+3)
    -   [Python :: 3.10](/search/?c=Programming+Language+%3A%3A+Python+%3A%3A+3.10)
    -   [Python :: 3.11](/search/?c=Programming+Language+%3A%3A+Python+%3A%3A+3.11)
    -   [Python :: 3.12](/search/?c=Programming+Language+%3A%3A+Python+%3A%3A+3.12)
    -   [Python :: 3.13](/search/?c=Programming+Language+%3A%3A+Python+%3A%3A+3.13)
    -   [Python :: 3.14](/search/?c=Programming+Language+%3A%3A+Python+%3A%3A+3.14)
-   **Topic**
    -   [Software Development :: Libraries :: Python Modules](/search/?c=Topic+%3A%3A+Software+Development+%3A%3A+Libraries+%3A%3A+Python+Modules)

  

## Release history [Release notifications](/help/#project-release-notifications) | [RSS feed](/rss/project/sap-ai-sdk-gen/releases.xml)

This version

![](https://pypi.org/static/images/blue-cube.572a5bfb.svg)

[

6.7.0

Mar 30, 2026

](/project/sap-ai-sdk-gen/6.7.0/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

6.6.0

Mar 11, 2026

](/project/sap-ai-sdk-gen/6.6.0/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

6.5.0

Mar 3, 2026

](/project/sap-ai-sdk-gen/6.5.0/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

6.1.2

Feb 3, 2026

](/project/sap-ai-sdk-gen/6.1.2/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

5.11.0

Feb 3, 2026

](/project/sap-ai-sdk-gen/5.11.0/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

5.10.0

Dec 16, 2025

](/project/sap-ai-sdk-gen/5.10.0/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

5.9.0

Dec 1, 2025

](/project/sap-ai-sdk-gen/5.9.0/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

5.8.0

Oct 30, 2025

](/project/sap-ai-sdk-gen/5.8.0/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

5.7.5

Oct 6, 2025

](/project/sap-ai-sdk-gen/5.7.5/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

5.6.3

Sep 12, 2025

](/project/sap-ai-sdk-gen/5.6.3/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

5.5.0

Sep 2, 2025

](/project/sap-ai-sdk-gen/5.5.0/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

5.4.5

Aug 4, 2025

](/project/sap-ai-sdk-gen/5.4.5/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

5.4.2

Jul 7, 2025

](/project/sap-ai-sdk-gen/5.4.2/)

![](https://pypi.org/static/images/white-cube.2351a86c.svg)

[

5.3.4

Jun 23, 2025

](/project/sap-ai-sdk-gen/5.3.4/)

## Download files

Download the file for your platform. If you're not sure which to choose, learn more about [installing packages](https://packaging.python.org/tutorials/installing-packages/ "External link").

### Source Distributions

No source distribution files available for this release.See tutorial on [generating distribution archives](https://packaging.python.org/tutorials/packaging-projects/#generating-distribution-archives "External link").

### Built Distribution

Filter files by name, interpreter, ABI, and platform.

If you're not sure about the file name format, learn more about [wheel file names](https://packaging.python.org/en/latest/specifications/binary-distribution-format/ "External link").

The dropdown lists show the available interpreters, ABIs, and platforms.

Enable javascript to be able to filter the list of wheel files.

Copy a direct link to the current filters [](https://pypi.org/project/sap-ai-sdk-gen/#files)Copy

File name 

Interpreter Interpreter py3

ABI ABI none

Platform Platform any

[sap\_ai\_sdk\_gen-6.7.0-py3-none-any.whl](https://files.pythonhosted.org/packages/3b/ff/f461483d53f592d4795ee024ae6591bb06d1917e845c59487e017b1e2748/sap_ai_sdk_gen-6.7.0-py3-none-any.whl) (2.2 MB [view details](#sap_ai_sdk_gen-6.7.0-py3-none-any.whl))

Uploaded Mar 30, 2026 `Python 3`

## File details

Details for the file `sap_ai_sdk_gen-6.7.0-py3-none-any.whl`.

### File metadata

-   Download URL: [sap\_ai\_sdk\_gen-6.7.0-py3-none-any.whl](https://files.pythonhosted.org/packages/3b/ff/f461483d53f592d4795ee024ae6591bb06d1917e845c59487e017b1e2748/sap_ai_sdk_gen-6.7.0-py3-none-any.whl)
-   Upload date: Mar 30, 2026
-   Size: 2.2 MB
-   Tags: Python 3
-   Uploaded using Trusted Publishing? No
-   Uploaded via: twine/6.2.0 CPython/3.12.1

### File hashes

Hashes for sap\_ai\_sdk\_gen-6.7.0-py3-none-any.whl

Algorithm

Hash digest

SHA256

`5bc3c54b6bb36039db59a4c35069d6bc91409e8f8219654e707082e2cab74a4f`

Copy

MD5

`aad9f9a722ac3e451008dd4e4f885c6e`

Copy

BLAKE2b-256

`3bfff461483d53f592d4795ee024ae6591bb06d1917e845c59487e017b1e2748`

Copy

[See more details on using hashes here.](https://pip.pypa.io/en/stable/topics/secure-installs/#hash-checking-mode "External link")

![](/static/images/white-cube.2351a86c.svg)

## Help

-   [Installing packages](https://packaging.python.org/tutorials/installing-packages/ "External link")
-   [Uploading packages](https://packaging.python.org/tutorials/packaging-projects/ "External link")
-   [User guide](https://packaging.python.org/ "External link")
-   [Project name retention](https://www.python.org/dev/peps/pep-0541/ "External link")
-   [FAQs](/help/)

## About PyPI

-   [PyPI Blog](https://blog.pypi.org "External link")
-   [Infrastructure dashboard](https://dtdg.co/pypi "External link")
-   [Statistics](/stats/)
-   [Logos & trademarks](/trademarks/)
-   [Our sponsors](/sponsors/)

## Contributing to PyPI

-   [Bugs and feedback](/help/#feedback)
-   [Contribute on GitHub](https://github.com/pypi/warehouse "External link")
-   [Translate PyPI](https://hosted.weblate.org/projects/pypa/warehouse/ "External link")
-   [Sponsor PyPI](/sponsors/)
-   [Development credits](https://github.com/pypi/warehouse/graphs/contributors "External link")

## Using PyPI

-   [Terms of Service](https://policies.python.org/pypi.org/Terms-of-Service/ "External link")
-   [Report security issue](/security/)
-   [Code of conduct](https://policies.python.org/python.org/code-of-conduct/ "External link")
-   [Privacy Notice](https://policies.python.org/pypi.org/Privacy-Notice/ "External link")
-   [Acceptable Use Policy](https://policies.python.org/pypi.org/Acceptable-Use-Policy/ "External link")

---

Status: [all systems operational](https://status.python.org/ "External link")

Developed and maintained by the Python community, for the Python community.  
[Donate today!](https://donate.pypi.org)

"PyPI", "Python Package Index", and the blocks logos are registered [trademarks](/trademarks/) of the [Python Software Foundation](https://www.python.org/psf-landing).  

© 2026 [Python Software Foundation](https://www.python.org/psf-landing/ "External link")  
[Site map](/sitemap/)

Switch to desktop version

-   English
-   español
-   français
-   日本語
-   português (Brasil)
-   українська
-   Ελληνικά
-   Deutsch
-   中文 (简体)
-   中文 (繁體)
-   русский
-   עברית
-   Esperanto
-   한국어

Supported by

 [![](https://pypi-camo.freetls.fastly.net/ed7074cadad1a06f56bc520ad9bd3e00d0704c5b/68747470733a2f2f73746f726167652e676f6f676c65617069732e636f6d2f707970692d6173736574732f73706f6e736f726c6f676f732f6177732d77686974652d6c6f676f2d7443615473387a432e706e67) AWS Cloud computing and Security Sponsor](https://aws.amazon.com/)[![](https://pypi-camo.freetls.fastly.net/8855f7c063a3bdb5b0ce8d91bfc50cf851cc5c51/68747470733a2f2f73746f726167652e676f6f676c65617069732e636f6d2f707970692d6173736574732f73706f6e736f726c6f676f732f64617461646f672d77686974652d6c6f676f2d6668644c4e666c6f2e706e67) Datadog Monitoring ](https://www.datadoghq.com/)[![](https://pypi-camo.freetls.fastly.net/60f709d24f3e4d469f9adc77c65e2f5291a3d165/68747470733a2f2f73746f726167652e676f6f676c65617069732e636f6d2f707970692d6173736574732f73706f6e736f726c6f676f732f6465706f742d77686974652d6c6f676f2d7038506f476831302e706e67) Depot Continuous Integration ](https://depot.dev)[![](https://pypi-camo.freetls.fastly.net/df6fe8829cbff2d7f668d98571df1fd011f36192/68747470733a2f2f73746f726167652e676f6f676c65617069732e636f6d2f707970692d6173736574732f73706f6e736f726c6f676f732f666173746c792d77686974652d6c6f676f2d65684d3077735f6f2e706e67) Fastly CDN ](https://www.fastly.com/)[![](https://pypi-camo.freetls.fastly.net/420cc8cf360bac879e24c923b2f50ba7d1314fb0/68747470733a2f2f73746f726167652e676f6f676c65617069732e636f6d2f707970692d6173736574732f73706f6e736f726c6f676f732f676f6f676c652d77686974652d6c6f676f2d616734424e3774332e706e67) Google Download Analytics ](https://careers.google.com/)[![](https://pypi-camo.freetls.fastly.net/d01053c02f3a626b73ffcb06b96367fdbbf9e230/68747470733a2f2f73746f726167652e676f6f676c65617069732e636f6d2f707970692d6173736574732f73706f6e736f726c6f676f732f70696e67646f6d2d77686974652d6c6f676f2d67355831547546362e706e67) Pingdom Monitoring ](https://www.pingdom.com/)[![](https://pypi-camo.freetls.fastly.net/67af7117035e2345bacb5a82e9aa8b5b3e70701d/68747470733a2f2f73746f726167652e676f6f676c65617069732e636f6d2f707970692d6173736574732f73706f6e736f726c6f676f732f73656e7472792d77686974652d6c6f676f2d4a2d6b64742d706e2e706e67) Sentry Error logging ](https://sentry.io/for/python/?utm_source=pypi&utm_medium=paid-community&utm_campaign=python-na-evergreen&utm_content=static-ad-pypi-sponsor-learnmore)[![](https://pypi-camo.freetls.fastly.net/b611884ff90435a0575dbab7d9b0d3e60f136466/68747470733a2f2f73746f726167652e676f6f676c65617069732e636f6d2f707970692d6173736574732f73706f6e736f726c6f676f732f737461747573706167652d77686974652d6c6f676f2d5467476c6a4a2d502e706e67) StatusPage Status page](https://statuspage.io)
```

**Tool: webfetch**

**Input:**
```json
{
  "url": "https://help.sap.com/docs/sap-ai-core/sap-ai-core-service-guide/available-models",
  "format": "markdown"
}
```

**Output:**
```
   SAP Help Portal | SAP Online Help
```

---

## Assistant (Code · anthropic--claude-4.6-sonnet · 4.5s)

**Tool: webfetch**

**Input:**
```json
{
  "url": "https://help.sap.com/doc/generative-ai-hub-sdk/CLOUD/en-US/index.html",
  "format": "markdown"
}
```

**Output:**
```
      SAP Cloud SDK for AI (Python) - generative | SAP Cloud SDK for AI (Python) - generative v6.7.0                      

[Skip to content](#content)

[SAP Cloud SDK for AI (Python) - generative v6.7.0](#)

Toggle navigation menu

 ⌘ K

[SAP Cloud SDK for AI (Python) - generative v6.7.0](#)

-   [Introduction](_reference/README_sphynx.html)
-   [Examples](examples.html)
    -   [Native Client Integrations](_reference/gen_ai_hub.html)
    -   [Langchain Integration](_reference/gen_ai_hub.html#langchain-integration)
    -   [SAP RPT-1 Models](_reference/gen_ai_hub.html#sap-rpt-1-models)
    -   [Using New Models Before Official SDK Support](_reference/gen_ai_hub.html#using-new-models-before-official-sdk-support)
    -   [Streaming](_reference/streaming.html)
    -   [Prompt Registry](_reference/prompt-registry.html)
    -   [Orchestration Service \[Deprecated\]](_reference/orchestration-service.html)
    -   [Orchestration Service V2 API](_reference/orchestration-service2.html)
    -   [Document Grounding](_reference/document-grounding.html)
    -   [Async examples](_reference/async-examples.html)
    -   [Generative AI Custom Evaluation](_reference/evaluations.html)
-   [Release Notes](_reference/RELEASE_NOTES.html)
-   [API Reference](_api_doc/gen_ai_hub.html)
    -   [gen\_ai\_hub.document\_grounding package](_api_doc/gen_ai_hub.document_grounding.html)
        -   [gen\_ai\_hub.document\_grounding.clients package](_api_doc/gen_ai_hub.document_grounding.clients.html)
        -   [gen\_ai\_hub.document\_grounding.models package](_api_doc/gen_ai_hub.document_grounding.models.html)
    -   [gen\_ai\_hub.evaluations package](_api_doc/gen_ai_hub.evaluations.html)
        -   [gen\_ai\_hub.evaluations.exceptions package](_api_doc/gen_ai_hub.evaluations.exceptions.html)
        -   [gen\_ai\_hub.evaluations.helpers package](_api_doc/gen_ai_hub.evaluations.helpers.html)
        -   [gen\_ai\_hub.evaluations.models package](_api_doc/gen_ai_hub.evaluations.models.html)
        -   [gen\_ai\_hub.evaluations.utils package](_api_doc/gen_ai_hub.evaluations.utils.html)
    -   [gen\_ai\_hub.orchestration package](_api_doc/gen_ai_hub.orchestration.html)
        -   [gen\_ai\_hub.orchestration.models package](_api_doc/gen_ai_hub.orchestration.models.html)
    -   [gen\_ai\_hub.orchestration\_v2 package](_api_doc/gen_ai_hub.orchestration_v2.html)
        -   [gen\_ai\_hub.orchestration\_v2.models package](_api_doc/gen_ai_hub.orchestration_v2.models.html)
    -   [gen\_ai\_hub.prompt\_registry package](_api_doc/gen_ai_hub.prompt_registry.html)
        -   [gen\_ai\_hub.prompt\_registry.models package](_api_doc/gen_ai_hub.prompt_registry.models.html)
    -   [gen\_ai\_hub.proxy package](_api_doc/gen_ai_hub.proxy.html)
        -   [gen\_ai\_hub.proxy.core package](_api_doc/gen_ai_hub.proxy.core.html)
        -   [gen\_ai\_hub.proxy.gen\_ai\_hub\_proxy package](_api_doc/gen_ai_hub.proxy.gen_ai_hub_proxy.html)
        -   [gen\_ai\_hub.proxy.langchain package](_api_doc/gen_ai_hub.proxy.langchain.html)
        -   [gen\_ai\_hub.proxy.native package](_api_doc/gen_ai_hub.proxy.native.html)
            -   [gen\_ai\_hub.proxy.native.amazon package](_api_doc/gen_ai_hub.proxy.native.amazon.html)
            -   [gen\_ai\_hub.proxy.native.google\_genai package](_api_doc/gen_ai_hub.proxy.native.google_genai.html)
            -   [gen\_ai\_hub.proxy.native.openai package](_api_doc/gen_ai_hub.proxy.native.openai.html)
            -   [gen\_ai\_hub.proxy.native.sap package](_api_doc/gen_ai_hub.proxy.native.sap.html)

# SAP Cloud SDK for AI (Python) - generative

-   [Introduction](_reference/README_sphynx.html)
    -   [Installation](_reference/README_sphynx.html#installation)
    -   [Configuration](_reference/README_sphynx.html#configuration)
        -   [Environment variables](_reference/README_sphynx.html#environment-variables)
        -   [Configuration files](_reference/README_sphynx.html#configuration-files)
    -   [Usage](_reference/README_sphynx.html#usage)
        -   [Prerequisite](_reference/README_sphynx.html#prerequisite)
        -   [Examples](_reference/README_sphynx.html#examples)
    -   [Supported Models](_reference/README_sphynx.html#supported-models)
        -   [LLM Models](_reference/README_sphynx.html#llm-models)
        -   [Embedding Models](_reference/README_sphynx.html#embedding-models)
        -   [Notes on model usage](_reference/README_sphynx.html#notes-on-model-usage)
    -   [Package dependencies](_reference/README_sphynx.html#package-dependencies)
-   [Examples](examples.html)
    -   [Native Client Integrations](_reference/gen_ai_hub.html)
        -   [Completions](_reference/gen_ai_hub.html#completions)
            -   [OpenAI](_reference/gen_ai_hub.html#openai)
                -   [Structured model outputs](_reference/gen_ai_hub.html#structured-model-outputs)
            -   [Google GenAI](_reference/gen_ai_hub.html#google-genai)
            -   [Amazon](_reference/gen_ai_hub.html#amazon)
        -   [Embeddings](_reference/gen_ai_hub.html#embeddings)
            -   [OpenAI](_reference/gen_ai_hub.html#id1)
            -   [Amazon](_reference/gen_ai_hub.html#id2)
    -   [Langchain Integration](_reference/gen_ai_hub.html#langchain-integration)
        -   [Harmonized Model Initialization](_reference/gen_ai_hub.html#harmonized-model-initialization)
        -   [LLM](_reference/gen_ai_hub.html#llm)
        -   [Chat model](_reference/gen_ai_hub.html#chat-model)
            -   [Structured model outputs](_reference/gen_ai_hub.html#id3)
        -   [Embeddings](_reference/gen_ai_hub.html#id4)
    -   [SAP RPT-1 Models](_reference/gen_ai_hub.html#sap-rpt-1-models)
        -   [Example of usage RPTClient for the regression task](_reference/gen_ai_hub.html#example-of-usage-rptclient-for-the-regression-task)
        -   [Example of usage RPTClient for the classification task](_reference/gen_ai_hub.html#example-of-usage-rptclient-for-the-classification-task)
        -   [Example of async usage of RPTClient](_reference/gen_ai_hub.html#example-of-async-usage-of-rptclient)
    -   [Using New Models Before Official SDK Support](_reference/gen_ai_hub.html#using-new-models-before-official-sdk-support)
    -   [Streaming](_reference/streaming.html)
        -   [Native SDKs](_reference/streaming.html#native-sdks)
            -   [OpenAI - ChatGPT](_reference/streaming.html#openai-chatgpt)
                -   [Structured model outputs](_reference/streaming.html#structured-model-outputs)
            -   [Google - GenAI](_reference/streaming.html#google-genai)
            -   [Anthropic - Claude](_reference/streaming.html#anthropic-claude)
            -   [Amazon - Bedrock](_reference/streaming.html#amazon-bedrock)
        -   [Langchain](_reference/streaming.html#langchain)
    -   [Prompt Registry](_reference/prompt-registry.html)
        -   [Prerequisite](_reference/prompt-registry.html#prerequisite)
            -   [Provide the credentials to authenticate the client and establish a connection with the Prompt Registry API.](_reference/prompt-registry.html#provide-the-credentials-to-authenticate-the-client-and-establish-a-connection-with-the-prompt-registry-api)
        -   [Prompt Template Management](_reference/prompt-registry.html#prompt-template-management)
            -   [Step 0: Initialize Client](_reference/prompt-registry.html#step-0-initialize-client)
                -   [Initialize the client to interact with the Prompt Registry.](_reference/prompt-registry.html#initialize-the-client-to-interact-with-the-prompt-registry)
            -   [Step 1: Create Prompt Templates](_reference/prompt-registry.html#step-1-create-prompt-templates)
                -   [Define the Prompt Template configuration and post to Prompt Registry.](_reference/prompt-registry.html#define-the-prompt-template-configuration-and-post-to-prompt-registry)
            -   [Step 2: Retrieve Prompt Templates](_reference/prompt-registry.html#step-2-retrieve-prompt-templates)
                -   [Retrieve the Prompt Template by ID.](_reference/prompt-registry.html#retrieve-the-prompt-template-by-id)
            -   [Step 3: Modify the Prompt Template](_reference/prompt-registry.html#step-3-modify-the-prompt-template)
                -   [We will add an input variable to the existing Prompt Template.](_reference/prompt-registry.html#we-will-add-an-input-variable-to-the-existing-prompt-template)
            -   [Step 4: Prompt Template History](_reference/prompt-registry.html#step-4-prompt-template-history)
                -   [Retrieve the history of Prompt Templates by scenario, name and version.](_reference/prompt-registry.html#retrieve-the-history-of-prompt-templates-by-scenario-name-and-version)
            -   [Step 5: Fill Prompt Template](_reference/prompt-registry.html#step-5-fill-prompt-template)
                -   [Fill the variables in the Prompt Template.](_reference/prompt-registry.html#fill-the-variables-in-the-prompt-template)
        -   [Orchestration Config Management](_reference/prompt-registry.html#orchestration-config-management)
            -   [Step 0: Initialize Client](_reference/prompt-registry.html#id1)
                -   [Initialize the client to interact with the Prompt Registry.](_reference/prompt-registry.html#id2)
            -   [Step 1: Create Orchestration Config](_reference/prompt-registry.html#step-1-create-orchestration-config)
                -   [Define the Orchestration Config configuration and post to Prompt Registry.](_reference/prompt-registry.html#define-the-orchestration-config-configuration-and-post-to-prompt-registry)
            -   [Step 2: Retrieve Orchestration Config](_reference/prompt-registry.html#step-2-retrieve-orchestration-config)
                -   [Retrieve the Orchestration Config by ID.](_reference/prompt-registry.html#retrieve-the-orchestration-config-by-id)
                -   [Retrieve the Orchestration Configs by scenario, name and version..](_reference/prompt-registry.html#retrieve-the-orchestration-configs-by-scenario-name-and-version)
            -   [Step 3: Orchestration Config History](_reference/prompt-registry.html#step-3-orchestration-config-history)
                -   [Retrieve the history of Orchestration Config by scenario, name and version.](_reference/prompt-registry.html#retrieve-the-history-of-orchestration-config-by-scenario-name-and-version)
            -   [Export Orchestration Config](_reference/prompt-registry.html#export-orchestration-config)
                -   [Export a design orchestration config in a declarative compatible yaml file.](_reference/prompt-registry.html#export-a-design-orchestration-config-in-a-declarative-compatible-yaml-file)
    -   [Orchestration Service \[Deprecated\]](_reference/orchestration-service.html)
        -   [Prerequisite](_reference/orchestration-service.html#prerequisite)
        -   [Authentication](_reference/orchestration-service.html#authentication)
        -   [Basic Orchestration Pipeline](_reference/orchestration-service.html#basic-orchestration-pipeline)
            -   [Step 1: Define the Template and Default Input Values](_reference/orchestration-service.html#step-1-define-the-template-and-default-input-values)
            -   [Step 2: Define the LLM](_reference/orchestration-service.html#step-2-define-the-llm)
            -   [Step 3: Create the Orchestration Configuration](_reference/orchestration-service.html#step-3-create-the-orchestration-configuration)
            -   [Step 4: Run the Orchestration Request](_reference/orchestration-service.html#step-4-run-the-orchestration-request)
                -   [Referencing Templates in the Prompt Registry](_reference/orchestration-service.html#referencing-templates-in-the-prompt-registry)
                -   [Overview of response\_format Parameter Options](_reference/orchestration-service.html#overview-of-response-format-parameter-options)
        -   [Understanding Deployment Resolution](_reference/orchestration-service.html#understanding-deployment-resolution)
            -   [Default Behavior](_reference/orchestration-service.html#default-behavior)
            -   [Direct Deployment Specification](_reference/orchestration-service.html#direct-deployment-specification)
            -   [Config-Based Specification](_reference/orchestration-service.html#config-based-specification)
        -   [Optional Modules](_reference/orchestration-service.html#optional-modules)
            -   [Data Masking](_reference/orchestration-service.html#data-masking)
                -   [Masking Types](_reference/orchestration-service.html#masking-types)
                -   [Configuration Options](_reference/orchestration-service.html#configuration-options)
            -   [Content Filtering](_reference/orchestration-service.html#content-filtering)
        -   [Streaming](_reference/orchestration-service.html#streaming)
        -   [Tool Calling (Function Calling)](_reference/orchestration-service.html#tool-calling-function-calling)
            -   [Defining Tools](_reference/orchestration-service.html#defining-tools)
                -   [Using the Python Decorator](_reference/orchestration-service.html#using-the-python-decorator)
                -   [Using the `FunctionTool` Class](_reference/orchestration-service.html#using-the-functiontool-class)
                -   [Using a JSON Schema Dictionary](_reference/orchestration-service.html#using-a-json-schema-dictionary)
            -   [Synchronous Tool Call Workflow](_reference/orchestration-service.html#synchronous-tool-call-workflow)
            -   [Streaming Tool Calls](_reference/orchestration-service.html#streaming-tool-calls)
        -   [Using Images as Input](_reference/orchestration-service.html#using-images-as-input)
            -   [1\. Preparing Image Inputs](_reference/orchestration-service.html#preparing-image-inputs)
                -   [a) From a URL or Data URL](_reference/orchestration-service.html#a-from-a-url-or-data-url)
                -   [b) From a Local File](_reference/orchestration-service.html#b-from-a-local-file)
            -   [2\. Adding Images to a Prompt](_reference/orchestration-service.html#adding-images-to-a-prompt)
        -   [Translation](_reference/orchestration-service.html#translation)
        -   [Advanced Examples](_reference/orchestration-service.html#advanced-examples)
            -   [Translation Service](_reference/orchestration-service.html#translation-service)
            -   [Chatbot with Memory](_reference/orchestration-service.html#chatbot-with-memory)
            -   [Sentiment Analysis with Few Shot Learning](_reference/orchestration-service.html#sentiment-analysis-with-few-shot-learning)
        -   [Async Support](_reference/orchestration-service.html#async-support)
    -   [Orchestration Service V2 API](_reference/orchestration-service2.html)
        -   [Prerequisite](_reference/orchestration-service2.html#prerequisite)
        -   [Authentication](_reference/orchestration-service2.html#authentication)
        -   [Basic Orchestration Pipeline](_reference/orchestration-service2.html#basic-orchestration-pipeline)
            -   [Step 1: Define the Template and Default Input Values](_reference/orchestration-service2.html#step-1-define-the-template-and-default-input-values)
            -   [Step 2: Define the LLM](_reference/orchestration-service2.html#step-2-define-the-llm)
            -   [Step 3: Create the Orchestration Configuration](_reference/orchestration-service2.html#step-3-create-the-orchestration-configuration)
            -   [Step 4: Run the Orchestration Request](_reference/orchestration-service2.html#step-4-run-the-orchestration-request)
                -   [Referencing Templates in the Prompt Registry](_reference/orchestration-service2.html#referencing-templates-in-the-prompt-registry)
                -   [Overview of response\_format Parameter Options](_reference/orchestration-service2.html#overview-of-response-format-parameter-options)
        -   [Understanding Deployment Resolution](_reference/orchestration-service2.html#understanding-deployment-resolution)
            -   [Default Behavior](_reference/orchestration-service2.html#default-behavior)
            -   [Direct Deployment Specification](_reference/orchestration-service2.html#direct-deployment-specification)
            -   [Config-Based Specification](_reference/orchestration-service2.html#config-based-specification)
        -   [Optional Modules](_reference/orchestration-service2.html#optional-modules)
            -   [Data Masking](_reference/orchestration-service2.html#data-masking)
                -   [Masking Types](_reference/orchestration-service2.html#masking-types)
                -   [Configuration Options](_reference/orchestration-service2.html#configuration-options)
            -   [Content Filtering](_reference/orchestration-service2.html#content-filtering)
        -   [Streaming](_reference/orchestration-service2.html#streaming)
        -   [Tool Calling (Function Calling)](_reference/orchestration-service2.html#tool-calling-function-calling)
            -   [Defining Tools](_reference/orchestration-service2.html#defining-tools)
                -   [Using the Python Decorator](_reference/orchestration-service2.html#using-the-python-decorator)
                -   [Using the `FunctionTool` Class](_reference/orchestration-service2.html#using-the-functiontool-class)
                -   [Using a JSON Schema Dictionary](_reference/orchestration-service2.html#using-a-json-schema-dictionary)
            -   [Synchronous Tool Call Workflow](_reference/orchestration-service2.html#synchronous-tool-call-workflow)
            -   [Streaming Tool Calls](_reference/orchestration-service2.html#streaming-tool-calls)
        -   [Using Images as Input](_reference/orchestration-service2.html#using-images-as-input)
            -   [1\. Preparing Image Inputs](_reference/orchestration-service2.html#preparing-image-inputs)
                -   [a) From a URL or Data URL](_reference/orchestration-service2.html#a-from-a-url-or-data-url)
                -   [b) From a Local File](_reference/orchestration-service2.html#b-from-a-local-file)
            -   [2\. Adding Images to a Prompt](_reference/orchestration-service2.html#adding-images-to-a-prompt)
        -   [Translation](_reference/orchestration-service2.html#translation)
        -   [Advanced Examples](_reference/orchestration-service2.html#advanced-examples)
            -   [Translation Service](_reference/orchestration-service2.html#translation-service)
            -   [Chatbot with Memory](_reference/orchestration-service2.html#chatbot-with-memory)
            -   [Sentiment Analysis with Few Shot Learning](_reference/orchestration-service2.html#sentiment-analysis-with-few-shot-learning)
        -   [Async Support](_reference/orchestration-service2.html#async-support)
        -   [Embeddings](_reference/orchestration-service2.html#embeddings)
            -   [Basic Usage](_reference/orchestration-service2.html#basic-usage)
            -   [Customizing Embedding Parameters](_reference/orchestration-service2.html#customizing-embedding-parameters)
            -   [Batch Embeddings](_reference/orchestration-service2.html#batch-embeddings)
            -   [Input Type Hints (Asymmetric Search)](_reference/orchestration-service2.html#input-type-hints-asymmetric-search)
            -   [Embeddings with Data Masking](_reference/orchestration-service2.html#embeddings-with-data-masking)
                -   [Masking with Custom Entities and Allowlist](_reference/orchestration-service2.html#masking-with-custom-entities-and-allowlist)
            -   [Async Embeddings](_reference/orchestration-service2.html#async-embeddings)
    -   [Document Grounding](_reference/document-grounding.html)
        -   [Prerequisites](_reference/document-grounding.html#prerequisites)
            -   [Create a Vector knowledge base](_reference/document-grounding.html#create-a-vector-knowledge-base)
        -   [Configuration of the Grounding Module](_reference/document-grounding.html#configuration-of-the-grounding-module)
            -   [Create the configuration](_reference/document-grounding.html#create-the-configuration)
                -   [Grounding configuration for searching SAP Help via elastic search](_reference/document-grounding.html#grounding-configuration-for-searching-sap-help-via-elastic-search)
                -   [Grounding configuration for searching a custom data repository](_reference/document-grounding.html#grounding-configuration-for-searching-a-custom-data-repository)
                -   [One can also show the retrieved context from the grounding module, which is added to the prompt for improving the response.](_reference/document-grounding.html#one-can-also-show-the-retrieved-context-from-the-grounding-module-which-is-added-to-the-prompt-for-improving-the-response)
                -   [Data Masking of the retrieved context](_reference/document-grounding.html#data-masking-of-the-retrieved-context)
    -   [Async examples](_reference/async-examples.html)
        -   [Async Amazon native](_reference/async-examples.html#async-amazon-native)
        -   [Async Function to Stream Amazon Model Response](_reference/async-examples.html#async-function-to-stream-amazon-model-response)
        -   [Async Function to Test Amazon Titan Embedding](_reference/async-examples.html#async-function-to-test-amazon-titan-embedding)
        -   [Async Google Genai native example](_reference/async-examples.html#async-google-genai-native-example)
        -   [Async Google GenAI Chat Example](_reference/async-examples.html#async-google-genai-chat-example)
        -   [Async Google GenAI Stream Generate Content Example](_reference/async-examples.html#async-google-genai-stream-generate-content-example)
        -   [Langchain examples](_reference/async-examples.html#langchain-examples)
        -   [Async Chat Streaming Example](_reference/async-examples.html#async-chat-streaming-example)
        -   [Chat Converse Model Example](_reference/async-examples.html#chat-converse-model-example)
        -   [Async Gemini Model Invocation Example](_reference/async-examples.html#async-gemini-model-invocation-example)
        -   [Async Gemini Streaming Example](_reference/async-examples.html#async-gemini-streaming-example)
    -   [Generative AI Custom Evaluation](_reference/evaluations.html)
        -   [Setup](_reference/evaluations.html#setup)
        -   [One Time Creation of Secrets](_reference/evaluations.html#one-time-creation-of-secrets)
        -   [Helper function to list available models in the region](_reference/evaluations.html#helper-function-to-list-available-models-in-the-region)
        -   [Helper function to see available System Defined Metrics](_reference/evaluations.html#helper-function-to-see-available-system-defined-metrics)
        -   [Defining the Evaluation Config](_reference/evaluations.html#defining-the-evaluation-config)
        -   [Helper function to generate Evaluation Config](_reference/evaluations.html#helper-function-to-generate-evaluation-config)
        -   [Running the evaluate function:](_reference/evaluations.html#running-the-evaluate-function)
        -   [Wait till each of the run is completed:](_reference/evaluations.html#wait-till-each-of-the-run-is-completed)
        -   [Debugging](_reference/evaluations.html#debugging)
        -   [Viewing the Aggregate Results](_reference/evaluations.html#viewing-the-aggregate-results)
        -   [Viewing the Completion Response](_reference/evaluations.html#viewing-the-completion-response)
        -   [Viewing the Metric Evaluation response](_reference/evaluations.html#viewing-the-metric-evaluation-response)
-   [Release Notes](_reference/RELEASE_NOTES.html)
    -   [6.7.0](_reference/RELEASE_NOTES.html#id1)
        -   [Features](_reference/RELEASE_NOTES.html#features)
        -   [Bugfixes](_reference/RELEASE_NOTES.html#bugfixes)
    -   [6.6.0](_reference/RELEASE_NOTES.html#id2)
        -   [Bugfixes](_reference/RELEASE_NOTES.html#id3)
    -   [6.5.0](_reference/RELEASE_NOTES.html#id4)
        -   [Features](_reference/RELEASE_NOTES.html#id5)
        -   [Bugfixes](_reference/RELEASE_NOTES.html#id6)
    -   [6.1.2](_reference/RELEASE_NOTES.html#id7)
        -   [Breaking Changes](_reference/RELEASE_NOTES.html#breaking-changes)
        -   [Features](_reference/RELEASE_NOTES.html#id8)
    -   [5.11.0](_reference/RELEASE_NOTES.html#id9)
        -   [Features](_reference/RELEASE_NOTES.html#id10)
    -   [5.10.0](_reference/RELEASE_NOTES.html#id11)
        -   [Features](_reference/RELEASE_NOTES.html#id12)
    -   [5.9.0](_reference/RELEASE_NOTES.html#id13)
        -   [Bugfixes](_reference/RELEASE_NOTES.html#id14)
    -   [5.8.0](_reference/RELEASE_NOTES.html#id15)
        -   [Features](_reference/RELEASE_NOTES.html#id16)
    -   [5.7.5](_reference/RELEASE_NOTES.html#id17)
        -   [Features](_reference/RELEASE_NOTES.html#id18)
        -   [Bugfixes](_reference/RELEASE_NOTES.html#id19)
    -   [5.6.3](_reference/RELEASE_NOTES.html#id20)
        -   [Features](_reference/RELEASE_NOTES.html#id21)
        -   [Bugfixes](_reference/RELEASE_NOTES.html#id22)
    -   [5.5.0](_reference/RELEASE_NOTES.html#id23)
        -   [Features](_reference/RELEASE_NOTES.html#id24)
        -   [Bugfixes](_reference/RELEASE_NOTES.html#id25)
    -   [5.4.5](_reference/RELEASE_NOTES.html#id26)
        -   [Features](_reference/RELEASE_NOTES.html#id27)
    -   [5.4.1](_reference/RELEASE_NOTES.html#id28)
        -   [Features](_reference/RELEASE_NOTES.html#id29)
    -   [5.3.4](_reference/RELEASE_NOTES.html#id30)
        -   [Breaking Changes](_reference/RELEASE_NOTES.html#id31)
        -   [Features](_reference/RELEASE_NOTES.html#id32)
        -   [Bugfixes](_reference/RELEASE_NOTES.html#id33)
    -   [4.12.1](_reference/RELEASE_NOTES.html#id34)
        -   [Features](_reference/RELEASE_NOTES.html#id35)
    -   [4.10.2](_reference/RELEASE_NOTES.html#id36)
        -   [Features](_reference/RELEASE_NOTES.html#id37)
    -   [4.4.3](_reference/RELEASE_NOTES.html#id38)
        -   [Features](_reference/RELEASE_NOTES.html#id39)
    -   [4.3.1](_reference/RELEASE_NOTES.html#id40)
        -   [Features](_reference/RELEASE_NOTES.html#id41)
        -   [Bugfixes](_reference/RELEASE_NOTES.html#id42)
    -   [4.1.1](_reference/RELEASE_NOTES.html#id43)
        -   [Features](_reference/RELEASE_NOTES.html#id44)
        -   [Bugfixes](_reference/RELEASE_NOTES.html#id45)
    -   [4.0.0](_reference/RELEASE_NOTES.html#id46)
        -   [Breaking Changes](_reference/RELEASE_NOTES.html#id47)
        -   [Features](_reference/RELEASE_NOTES.html#id48)
    -   [3.8.0](_reference/RELEASE_NOTES.html#id49)
        -   [Features](_reference/RELEASE_NOTES.html#id50)
    -   [3.2.6](_reference/RELEASE_NOTES.html#id51)
        -   [Features](_reference/RELEASE_NOTES.html#id52)
        -   [Bugfixes](_reference/RELEASE_NOTES.html#id53)
    -   [3.1.1](_reference/RELEASE_NOTES.html#id54)
        -   [Features](_reference/RELEASE_NOTES.html#id55)
    -   [3.1.0](_reference/RELEASE_NOTES.html#id56)
        -   [Breaking Changes](_reference/RELEASE_NOTES.html#id57)
        -   [Features](_reference/RELEASE_NOTES.html#id58)
-   [API Reference](_api_doc/gen_ai_hub.html)
    -   [`GenAIHubProxyClient`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient)
        -   [`GenAIHubProxyClient.add_foundation_model_scenario()`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.add_foundation_model_scenario)
        -   [`GenAIHubProxyClient.for_profile()`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.for_profile)
        -   [`GenAIHubProxyClient.init_client()`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.init_client)
        -   [`GenAIHubProxyClient.set_default_values()`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.set_default_values)
        -   [`GenAIHubProxyClient.get_additional_headers()`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.get_additional_headers)
        -   [`GenAIHubProxyClient.get_ai_core_token()`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.get_ai_core_token)
        -   [`GenAIHubProxyClient.get_deployments()`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.get_deployments)
        -   [`GenAIHubProxyClient.get_request_header()`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.get_request_header)
        -   [`GenAIHubProxyClient.model_post_init()`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.model_post_init)
        -   [`GenAIHubProxyClient.select_deployment()`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.select_deployment)
        -   [`GenAIHubProxyClient.set_headers_addition()`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.set_headers_addition)
        -   [`GenAIHubProxyClient.update_deployments()`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.update_deployments)
        -   [`GenAIHubProxyClient.AI_CLIENT_TYPE_VAL`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.AI_CLIENT_TYPE_VAL)
        -   [`GenAIHubProxyClient.ai_core_client`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.ai_core_client)
        -   [`GenAIHubProxyClient.auth_url`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.auth_url)
        -   [`GenAIHubProxyClient.base_url`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.base_url)
        -   [`GenAIHubProxyClient.client_id`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.client_id)
        -   [`GenAIHubProxyClient.client_secret`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.client_secret)
        -   [`GenAIHubProxyClient.default_values`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.default_values)
        -   [`GenAIHubProxyClient.deployment_class`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.deployment_class)
        -   [`GenAIHubProxyClient.deployments`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.deployments)
        -   [`GenAIHubProxyClient.foundational_model_scenarios`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.foundational_model_scenarios)
        -   [`GenAIHubProxyClient.model_config`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.model_config)
        -   [`GenAIHubProxyClient.on_invalid_deployments`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.on_invalid_deployments)
        -   [`GenAIHubProxyClient.request_header`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.request_header)
        -   [`GenAIHubProxyClient.resource_group`](_api_doc/gen_ai_hub.html#gen_ai_hub.GenAIHubProxyClient.resource_group)
    -   [Subpackages](_api_doc/gen_ai_hub.html#subpackages)
        -   [gen\_ai\_hub.document\_grounding package](_api_doc/gen_ai_hub.document_grounding.html)
            -   [Subpackages](_api_doc/gen_ai_hub.document_grounding.html#subpackages)
                -   [gen\_ai\_hub.document\_grounding.clients package](_api_doc/gen_ai_hub.document_grounding.clients.html)
                    -   [Submodules](_api_doc/gen_ai_hub.document_grounding.clients.html#submodules)
                    -   [gen\_ai\_hub.document\_grounding.clients.pipeline\_api\_client module](_api_doc/gen_ai_hub.document_grounding.clients.html#module-gen_ai_hub.document_grounding.clients.pipeline_api_client)
                        -   [`PipelineAPIClient`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.pipeline_api_client.PipelineAPIClient)
                            -   [`PipelineAPIClient.__init__()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.pipeline_api_client.PipelineAPIClient.__init__)
                            -   [`PipelineAPIClient.create_pipeline()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.pipeline_api_client.PipelineAPIClient.create_pipeline)
                            -   [`PipelineAPIClient.delete_pipeline_by_id()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.pipeline_api_client.PipelineAPIClient.delete_pipeline_by_id)
                            -   [`PipelineAPIClient.get_execution_document_by_id()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.pipeline_api_client.PipelineAPIClient.get_execution_document_by_id)
                            -   [`PipelineAPIClient.get_execution_documents()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.pipeline_api_client.PipelineAPIClient.get_execution_documents)
                            -   [`PipelineAPIClient.get_pipeline_by_id()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.pipeline_api_client.PipelineAPIClient.get_pipeline_by_id)
                            -   [`PipelineAPIClient.get_pipeline_document_by_id()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.pipeline_api_client.PipelineAPIClient.get_pipeline_document_by_id)
                            -   [`PipelineAPIClient.get_pipeline_documents()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.pipeline_api_client.PipelineAPIClient.get_pipeline_documents)
                            -   [`PipelineAPIClient.get_pipeline_execution_by_id()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.pipeline_api_client.PipelineAPIClient.get_pipeline_execution_by_id)
                            -   [`PipelineAPIClient.get_pipeline_executions()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.pipeline_api_client.PipelineAPIClient.get_pipeline_executions)
                            -   [`PipelineAPIClient.get_pipeline_status()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.pipeline_api_client.PipelineAPIClient.get_pipeline_status)
                            -   [`PipelineAPIClient.get_pipelines()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.pipeline_api_client.PipelineAPIClient.get_pipelines)
                            -   [`PipelineAPIClient.search_pipelines()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.pipeline_api_client.PipelineAPIClient.search_pipelines)
                            -   [`PipelineAPIClient.trigger_pipeline()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.pipeline_api_client.PipelineAPIClient.trigger_pipeline)
                    -   [gen\_ai\_hub.document\_grounding.clients.retrieval\_api\_client module](_api_doc/gen_ai_hub.document_grounding.clients.html#module-gen_ai_hub.document_grounding.clients.retrieval_api_client)
                        -   [`RetrievalAPIClient`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.retrieval_api_client.RetrievalAPIClient)
                            -   [`RetrievalAPIClient.__init__()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.retrieval_api_client.RetrievalAPIClient.__init__)
                            -   [`RetrievalAPIClient.get_data_repositories()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.retrieval_api_client.RetrievalAPIClient.get_data_repositories)
                            -   [`RetrievalAPIClient.get_data_repository_by_id()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.retrieval_api_client.RetrievalAPIClient.get_data_repository_by_id)
                            -   [`RetrievalAPIClient.search()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.retrieval_api_client.RetrievalAPIClient.search)
                    -   [gen\_ai\_hub.document\_grounding.clients.vector\_api\_client module](_api_doc/gen_ai_hub.document_grounding.clients.html#module-gen_ai_hub.document_grounding.clients.vector_api_client)
                        -   [`VectorAPIClient`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.vector_api_client.VectorAPIClient)
                            -   [`VectorAPIClient.__init__()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.vector_api_client.VectorAPIClient.__init__)
                            -   [`VectorAPIClient.create_collection()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.vector_api_client.VectorAPIClient.create_collection)
                            -   [`VectorAPIClient.create_documents()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.vector_api_client.VectorAPIClient.create_documents)
                            -   [`VectorAPIClient.delete_collection()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.vector_api_client.VectorAPIClient.delete_collection)
                            -   [`VectorAPIClient.delete_document()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.vector_api_client.VectorAPIClient.delete_document)
                            -   [`VectorAPIClient.get_collection_by_id()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.vector_api_client.VectorAPIClient.get_collection_by_id)
                            -   [`VectorAPIClient.get_collection_creation_status()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.vector_api_client.VectorAPIClient.get_collection_creation_status)
                            -   [`VectorAPIClient.get_collection_deletion_status()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.vector_api_client.VectorAPIClient.get_collection_deletion_status)
                            -   [`VectorAPIClient.get_collections()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.vector_api_client.VectorAPIClient.get_collections)
                            -   [`VectorAPIClient.get_document_by_id()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.vector_api_client.VectorAPIClient.get_document_by_id)
                            -   [`VectorAPIClient.get_documents()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.vector_api_client.VectorAPIClient.get_documents)
                            -   [`VectorAPIClient.search()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.vector_api_client.VectorAPIClient.search)
                            -   [`VectorAPIClient.update_documents()`](_api_doc/gen_ai_hub.document_grounding.clients.html#gen_ai_hub.document_grounding.clients.vector_api_client.VectorAPIClient.update_documents)
                -   [gen\_ai\_hub.document\_grounding.models package](_api_doc/gen_ai_hub.document_grounding.models.html)
                    -   [Submodules](_api_doc/gen_ai_hub.document_grounding.models.html#submodules)
                    -   [gen\_ai\_hub.document\_grounding.models.pipeline module](_api_doc/gen_ai_hub.document_grounding.models.html#module-gen_ai_hub.document_grounding.models.pipeline)
                        -   [`BasePipelineResponse`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.BasePipelineResponse)
                            -   [`BasePipelineResponse.id`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.BasePipelineResponse.id)
                            -   [`BasePipelineResponse.metadata`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.BasePipelineResponse.metadata)
                            -   [`BasePipelineResponse.model_config`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.BasePipelineResponse.model_config)
                            -   [`BasePipelineResponse.type`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.BasePipelineResponse.type)
                        -   [`CommonConfiguration`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.CommonConfiguration)
                            -   [`CommonConfiguration.destination`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.CommonConfiguration.destination)
                            -   [`CommonConfiguration.model_config`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.CommonConfiguration.model_config)
                        -   [`DataRepositoryMetadataItem`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.DataRepositoryMetadataItem)
                            -   [`DataRepositoryMetadataItem.key`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.DataRepositoryMetadataItem.key)
                            -   [`DataRepositoryMetadataItem.model_config`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.DataRepositoryMetadataItem.model_config)
                            -   [`DataRepositoryMetadataItem.value`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.DataRepositoryMetadataItem.value)
                        -   [`Document`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.Document)
                            -   [`Document.absoluteUrl`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.Document.absoluteUrl)
                            -   [`Document.createdTimestamp`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.Document.createdTimestamp)
                            -   [`Document.downloadLocation`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.Document.downloadLocation)
                            -   [`Document.id`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.Document.id)
                            -   [`Document.lastUpdatedTimestamp`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.Document.lastUpdatedTimestamp)
                            -   [`Document.metadataId`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.Document.metadataId)
                            -   [`Document.model_config`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.Document.model_config)
                            -   [`Document.status`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.Document.status)
                            -   [`Document.title`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.Document.title)
                            -   [`Document.viewLocation`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.Document.viewLocation)
                        -   [`DocumentStatus`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.DocumentStatus)
                            -   [`DocumentStatus.__new__()`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.DocumentStatus.__new__)
                            -   [`DocumentStatus.DEINDEXED`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.DocumentStatus.DEINDEXED)
                            -   [`DocumentStatus.FAILED`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.DocumentStatus.FAILED)
                            -   [`DocumentStatus.FAILED_TO_BE_RETRIED`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.DocumentStatus.FAILED_TO_BE_RETRIED)
                            -   [`DocumentStatus.INDEXED`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.DocumentStatus.INDEXED)
                            -   [`DocumentStatus.REINDEXED`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.DocumentStatus.REINDEXED)
                            -   [`DocumentStatus.TO_BE_PROCESSED`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.DocumentStatus.TO_BE_PROCESSED)
                            -   [`DocumentStatus.TO_BE_SCHEDULED`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.DocumentStatus.TO_BE_SCHEDULED)
                        -   [`DocumentsStatusResponse`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.DocumentsStatusResponse)
                            -   [`DocumentsStatusResponse.count`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.DocumentsStatusResponse.count)
                            -   [`DocumentsStatusResponse.model_config`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.DocumentsStatusResponse.model_config)
                            -   [`DocumentsStatusResponse.resources`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.DocumentsStatusResponse.resources)
                        -   [`GetPipelineExecutionsResponse`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.GetPipelineExecutionsResponse)
                            -   [`GetPipelineExecutionsResponse.count`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.GetPipelineExecutionsResponse.count)
                            -   [`GetPipelineExecutionsResponse.model_config`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.GetPipelineExecutionsResponse.model_config)
                            -   [`GetPipelineExecutionsResponse.resources`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.GetPipelineExecutionsResponse.resources)
                        -   [`GetPipelineStatusResponse`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.GetPipelineStatusResponse)
                            -   [`GetPipelineStatusResponse.lastStarted`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.GetPipelineStatusResponse.lastStarted)
                            -   [`GetPipelineStatusResponse.model_config`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.GetPipelineStatusResponse.model_config)
                            -   [`GetPipelineStatusResponse.status`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.GetPipelineStatusResponse.status)
                        -   [`GetPipelinesResponse`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.GetPipelinesResponse)
                            -   [`GetPipelinesResponse.count`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.GetPipelinesResponse.count)
                            -   [`GetPipelinesResponse.model_config`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.GetPipelinesResponse.model_config)
                            -   [`GetPipelinesResponse.resources`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.GetPipelinesResponse.resources)
                        -   [`MSSharePointConfiguration`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.MSSharePointConfiguration)
                            -   [`MSSharePointConfiguration.destination`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.MSSharePointConfiguration.destination)
                            -   [`MSSharePointConfiguration.model_config`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.MSSharePointConfiguration.model_config)
                            -   [`MSSharePointConfiguration.sharePoint`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.MSSharePointConfiguration.sharePoint)
                        -   [`MSSharePointConfigurationGetResponse`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.MSSharePointConfigurationGetResponse)
                            -   [`MSSharePointConfigurationGetResponse.destination`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.MSSharePointConfigurationGetResponse.destination)
                            -   [`MSSharePointConfigurationGetResponse.model_config`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.MSSharePointConfigurationGetResponse.model_config)
                            -   [`MSSharePointConfigurationGetResponse.sharePoint`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.MSSharePointConfigurationGetResponse.sharePoint)
                        -   [`MSSharePointPipelineCreateRequest`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.MSSharePointPipelineCreateRequest)
                            -   [`MSSharePointPipelineCreateRequest.configuration`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.MSSharePointPipelineCreateRequest.configuration)
                            -   [`MSSharePointPipelineCreateRequest.metadata`](_api_doc/gen_ai_hub.document_grounding.models.html#gen_ai_hub.document_grounding.models.pipeline.MSSharePointPipelineCreateRequest.metadata)

...404528 bytes truncated...

The tool call succeeded but the output was truncated. Full output saved to: /Users/sfuser/.local/share/kilo/tool-output/tool_da4630b63001PtZnUyG3OuBn1x
Use the Task tool to have explore agent process this file with Grep and Read (with offset/limit). Do NOT read the full file yourself - delegate to save context.
```

**Tool: webfetch**

**Input:**
```json
{
  "url": "https://github.com/SAP/ai-sdk-python",
  "format": "markdown"
}
```

**Error:**
```
Error: Request failed with status code: 404
```

---

## Assistant (Code · anthropic--claude-4.6-sonnet · 4.0s)

**Tool: webfetch**

**Input:**
```json
{
  "url": "https://help.sap.com/doc/generative-ai-hub-sdk/CLOUD/en-US/_reference/orchestration-service2.html",
  "format": "markdown"
}
```

**Output:**
```
      Orchestration Service V2 API | SAP Cloud SDK for AI (Python) - generative v6.7.0                       

[Skip to content](#content)

[SAP Cloud SDK for AI (Python) - generative v6.7.0](../index.html)

Toggle navigation menu

 ⌘ K

[SAP Cloud SDK for AI (Python) - generative v6.7.0](../index.html)

-   [Introduction](README_sphynx.html)
-   [Examples](../examples.html)
    -   [Native Client Integrations](gen_ai_hub.html)
    -   [Langchain Integration](gen_ai_hub.html#langchain-integration)
    -   [SAP RPT-1 Models](gen_ai_hub.html#sap-rpt-1-models)
    -   [Using New Models Before Official SDK Support](gen_ai_hub.html#using-new-models-before-official-sdk-support)
    -   [Streaming](streaming.html)
    -   [Prompt Registry](prompt-registry.html)
    -   [Orchestration Service \[Deprecated\]](orchestration-service.html)
    -   [Orchestration Service V2 API](#)
    -   [Document Grounding](document-grounding.html)
    -   [Async examples](async-examples.html)
    -   [Generative AI Custom Evaluation](evaluations.html)
-   [Release Notes](RELEASE_NOTES.html)
-   [API Reference](../_api_doc/gen_ai_hub.html)
    -   [gen\_ai\_hub.document\_grounding package](../_api_doc/gen_ai_hub.document_grounding.html)
        -   [gen\_ai\_hub.document\_grounding.clients package](../_api_doc/gen_ai_hub.document_grounding.clients.html)
        -   [gen\_ai\_hub.document\_grounding.models package](../_api_doc/gen_ai_hub.document_grounding.models.html)
    -   [gen\_ai\_hub.evaluations package](../_api_doc/gen_ai_hub.evaluations.html)
        -   [gen\_ai\_hub.evaluations.exceptions package](../_api_doc/gen_ai_hub.evaluations.exceptions.html)
        -   [gen\_ai\_hub.evaluations.helpers package](../_api_doc/gen_ai_hub.evaluations.helpers.html)
        -   [gen\_ai\_hub.evaluations.models package](../_api_doc/gen_ai_hub.evaluations.models.html)
        -   [gen\_ai\_hub.evaluations.utils package](../_api_doc/gen_ai_hub.evaluations.utils.html)
    -   [gen\_ai\_hub.orchestration package](../_api_doc/gen_ai_hub.orchestration.html)
        -   [gen\_ai\_hub.orchestration.models package](../_api_doc/gen_ai_hub.orchestration.models.html)
    -   [gen\_ai\_hub.orchestration\_v2 package](../_api_doc/gen_ai_hub.orchestration_v2.html)
        -   [gen\_ai\_hub.orchestration\_v2.models package](../_api_doc/gen_ai_hub.orchestration_v2.models.html)
    -   [gen\_ai\_hub.prompt\_registry package](../_api_doc/gen_ai_hub.prompt_registry.html)
        -   [gen\_ai\_hub.prompt\_registry.models package](../_api_doc/gen_ai_hub.prompt_registry.models.html)
    -   [gen\_ai\_hub.proxy package](../_api_doc/gen_ai_hub.proxy.html)
        -   [gen\_ai\_hub.proxy.core package](../_api_doc/gen_ai_hub.proxy.core.html)
        -   [gen\_ai\_hub.proxy.gen\_ai\_hub\_proxy package](../_api_doc/gen_ai_hub.proxy.gen_ai_hub_proxy.html)
        -   [gen\_ai\_hub.proxy.langchain package](../_api_doc/gen_ai_hub.proxy.langchain.html)
        -   [gen\_ai\_hub.proxy.native package](../_api_doc/gen_ai_hub.proxy.native.html)
            -   [gen\_ai\_hub.proxy.native.amazon package](../_api_doc/gen_ai_hub.proxy.native.amazon.html)
            -   [gen\_ai\_hub.proxy.native.google\_genai package](../_api_doc/gen_ai_hub.proxy.native.google_genai.html)
            -   [gen\_ai\_hub.proxy.native.openai package](../_api_doc/gen_ai_hub.proxy.native.openai.html)
            -   [gen\_ai\_hub.proxy.native.sap package](../_api_doc/gen_ai_hub.proxy.native.sap.html)

[SAP Cloud SDK for AI (Python) - generative v6.7.0](../index.html)

/

[Examples](../examples.html)

/

Orchestration Service V2 API

# Orchestration Service V2 API

This notebook demonstrates how to use the SDK to interact with the Orchestration Service V2, enabling the creation of AI-driven workflows by seamlessly integrating various modules, such as templating, large language models (LLMs), data masking and content filtering. By leveraging these modules, you can build complex, automated workflows that enhance the capabilities of your AI solutions. For more details on configuring and using these modules, please refer to the [Orchestration Service Documentation](https://help.sap.com/docs/ai-launchpad/sap-ai-launchpad/orchestration).

## Prerequisite

> **Important:** Before you begin using the SDK, make sure to set up a virtual deployment of the Orchestration Service.

For detailed guidance on setting up the Orchestration Service, please refer to the setup guide [here](https://help.sap.com/docs/ai-launchpad/sap-ai-launchpad/create-deployment-for-orchestration).

## Authentication

By default, the `OrchestrationService` initializes a `GenAIHubProxyClient`, which automatically configures credentials using configuration files or environment variables, as outlined in the *Introduction* section.

If you prefer to set credentials manually, you can provide a custom instance using the `proxy_client` parameter.

## Basic Orchestration Pipeline

Let's walk through a basic orchestration pipeline for a translation task.

### Step 1: Define the Template and Default Input Values

The `Template` class is used to define structured message templates for generating dynamic interactions with language models. In this example, the template is designed for a translation assistant, allowing users to specify a language and text for translation.

`from gen_ai_hub.orchestration_v2.models.message import SystemMessage, UserMessage from gen_ai_hub.orchestration_v2.models.template import Template template = Template(     template=[        SystemMessage(content="You are a helpful translation assistant."),        UserMessage(content="Translate the following text to {{?to_lang}}: {{?user_query}}"),    ],    defaults={"to_lang": "German"}    )`

This template can be used to create translation requests where the language and text to be translated are specified dynamically. The placeholders in the `UserMessage` will be replaced with the actual values provided at runtime, and the default value for the language is set to German.

### Step 2: Define the LLM

The `LLM` class is used to configure and initialize a language model for generating text based on specific parameters. In this example, we'll use the `gpt-4o` model to perform the translation task.

**Note:** The Orchestration Service automatically manages the virtual deployment of the language model, so no additional setup is needed on your end.

`from gen_ai_hub.orchestration_v2.models.llm_model_details import LLMModelDetails llm = LLMModelDetails(name="gpt-5-nano", params={"max_completion_tokens": 512})`

Initializes the language model to use the `gpt-5-nano` model. It will generate responses up to 512 tokens in length.

### Step 3: Create the Orchestration Configuration

The `OrchestrationConfig` class defines a configuration for integrating various modules, such as templates and language models, into a cohesive orchestration setup. It specifies how these components interact and are configured to achieve the desired operational scenario.

`from gen_ai_hub.orchestration_v2.models.template import PromptTemplatingModuleConfig from gen_ai_hub.orchestration_v2.models.config import ModuleConfig, OrchestrationConfig prompt_template = PromptTemplatingModuleConfig(prompt=template,                                                model=llm) module_config = ModuleConfig(prompt_templating=prompt_template) config = OrchestrationConfig(modules=module_config)`

### Step 4: Run the Orchestration Request

The `OrchestrationService` class is used to interact with a orchestration service instance by providing configuration details to initiate and manage its operations.

`from gen_ai_hub.orchestration_v2.service import OrchestrationService orchestration_service = OrchestrationService(config=config)`

Call the `run` method with the required `placeholder values`. The service will process the input according to the configuration and return the result.

`result = orchestration_service.run(placeholder_values={"user_query": "The Orchestration Service is working!"}) print(result.final_result.choices[0].message.content)`

#### Referencing Templates in the Prompt Registry

In Step 3 you can also use a prompt template reference, which allows you to reuse existing templates stored in the Prompt Registry.

`from gen_ai_hub.orchestration_v2.models.template_ref import TemplateRefByID, TemplateRefByScenarioNameVersion template_by_id = TemplateRefByID(id="648871d9-b207-441c-8c13-afee71b0dbec") # this is just an example id template_by_names = TemplateRefByScenarioNameVersion(scenario="translation", name="translate_text", version="0.1.0")`

#### Overview of response\_format Parameter Options

The `response_format` parameter allows the model output to be formatted in several predefined ways, as follows:

1.  **text**: This is the simplest form where the model's output is generated as plain text. It is suitable for applications that require raw text processing.
    
2.  **json\_object**: Under this setting, the model's output is structured as a JSON object. This is useful for applications that handle data in JSON format, enabling easy integration with web applications and APIs.
    
3.  **json\_schema**: This setting allows the model's output to adhere to a defined JSON schema. This is particularly useful for applications that require strict data validation, ensuring the output matches a predefined schema.
    

`from gen_ai_hub.orchestration_v2.models.message import SystemMessage, UserMessage from gen_ai_hub.orchestration_v2.models.template import Template from gen_ai_hub.orchestration_v2.models.response_format import ResponseFormatText template = Template(     template=[        SystemMessage(content="You are a helpful translation assistant."),        UserMessage(content="{{?user_query}}")    ],    response_format=ResponseFormatText(),    defaults={"user_query": "Who was the first person on the moon?"} ) # Response: # The first man on the moon was Neil Armstrong.`

`from gen_ai_hub.orchestration_v2.models.message import SystemMessage, UserMessage from gen_ai_hub.orchestration_v2.models.template import Template from gen_ai_hub.orchestration_v2.models.response_format import ResponseFormatJsonObject template = Template(     template=[        SystemMessage(content="You are a helpful translation assistant. Format the response as json."),        UserMessage(content="{{?user_query}}")    ],    response_format=ResponseFormatJsonObject(),    defaults={"user_query": "Who was the first person on the moon?"} ) # Response: # { #     "First_man_on_the_moon": "Neil Armstrong" # }`

**Important:** When using `response_format` as json\_object, ensure that messages contain the word 'json' in some form.

`from gen_ai_hub.orchestration_v2.models.message import SystemMessage, UserMessage from gen_ai_hub.orchestration_v2.models.template import Template from gen_ai_hub.orchestration_v2.models.response_format import ResponseFormatJsonSchema, JSONResponseSchema json_schema = {     "title": "Person",    "type": "object",    "properties": {            "firstName": {            "type": "string",            "description": "The person's first name."        },            "lastName": {            "type": "string",            "description": "The person's last name."        }    } } template = Template(     template=[        SystemMessage(content="You are a helpful translation assistant. Format the response as json."),        UserMessage(content="{{?user_query}}")    ],    response_format=ResponseFormatJsonSchema(                json_schema=JSONResponseSchema(                    name="person", description="person mapping", schema=json_schema                ),            ),    defaults={"user_query": "Who was the first person on the moon?"} ) # Response: # { #     "firstName": "Neil", #     "lastName": "Armstrong" # }`

## Understanding Deployment Resolution

The `OrchestrationService` class provides multiple ways to specify and target orchestration deployments when sending requests. Below are the available options:

### Default Behavior

If no parameters are provided, the `OrchestrationService` automatically searches for a `RUNNING` deployment. If multiple running deployments exist, the service selects the most recently created one.

### Direct Deployment Specification

You can explicitly define the target deployment using the following options:

1.  **API URL** (`api_url`):
    
    -   Specify the exact URL assigned to the deployment during its creation.
        
    -   Refer to the Prerequisites section for more details on obtaining the deployment URL.
        
2.  **Deployment ID** (`deployment_id`):
    
    -   Use the unique identifier assigned to the deployment instead of the URL.
        

### Config-Based Specification

If you want to target deployments based on their configuration source, use one of the following options:

1.  **Configuration ID** (`config_id`):
    
    -   The `OrchestrationService` searches for a `RUNNING` deployment created using the provided configuration ID.
        
2.  **Configuration Name** (`config_name`):
    
    -   The service looks for a `RUNNING` deployment that matches the specified configuration name.
        

If multiple deployments match the given configuration criteria, the most recently created one will be selected automatically.

## Optional Modules

### Data Masking

The `Data Masking` module `anonymizes` or `pseudonymizes` personally identifiable information (PII) before it is processed by the LLM module. Currently, `SAPDataPrivacyIntegration` is the only available masking provider.

#### Masking Types

-   **Anonymization**: All identifying information is replaced with placeholders (e.g., MASKED\_ENTITY), and the original data cannot be recovered, ensuring that no trace of the original information is retained.
    
-   **Pseudonymization**: Data is substituted with unique placeholders (e.g., MASKED\_ENTITY\_ID), allowing the original information to be restored if needed.
    

In both cases, the masking module identifies sensitive data and replaces it with appropriate placeholders before further processing.

#### Configuration Options

-   **entities**: Specify which types of entities to mask (e.g., EMAIL, PHONE, PERSON).
    
-   **allowlist**: Provide specific terms or patterns that should be excluded from masking, even if they match entity types.
    
-   **mask\_grounding\_input**: When enabled, ensures that masking is also applied to the context provided to the grounding module.
    

`from gen_ai_hub.orchestration_v2.utils import load_text_file from gen_ai_hub.orchestration_v2.models.message import SystemMessage, UserMessage from gen_ai_hub.orchestration_v2.models.template import Template, PromptTemplatingModuleConfig from gen_ai_hub.orchestration_v2.models.llm_model_details import LLMModelDetails from gen_ai_hub.orchestration_v2.models.config import ModuleConfig, OrchestrationConfig from gen_ai_hub.orchestration_v2.service import OrchestrationService from gen_ai_hub.orchestration_v2.models.data_masking import MaskingModuleConfig, MaskingProviderConfig, MaskingMethod, DPIStandardEntity, ProfileEntity orchestration_service = OrchestrationService() data_masking_config = MaskingModuleConfig(     providers=[MaskingProviderConfig(        method=MaskingMethod.ANONYMIZATION,        entities=[            DPIStandardEntity(type=ProfileEntity.ADDRESS),            DPIStandardEntity(type=ProfileEntity.EMAIL),            DPIStandardEntity(type=ProfileEntity.PHONE),            DPIStandardEntity(type=ProfileEntity.PERSON),        ],        allowlist=["M&K Group"],  # Terms to exclude from masking    )], ) template = Template(     template=[        SystemMessage(content="You are a helpful AI assistant."),        UserMessage(content="Summarize the following CV in 10 sentences: {{?orgCV}}"),    ]    ) llm=LLMModelDetails(name="gpt-4o") prompt_template = PromptTemplatingModuleConfig(prompt=template,                                                model=llm) module_config = ModuleConfig(prompt_templating=prompt_template, masking=data_masking_config) config = OrchestrationConfig(modules=module_config) cv_as_string = load_text_file("data/cv.txt") result = orchestration_service.run(     config=config,    placeholder_values={"orgCV": cv_as_string} )`

`print(result.final_result.choices[0].message.content)`

### Content Filtering

The `Content Filtering` module can be configured to filter both the `input` to the LLM module (input filter) and the `output` generated by the LLM (output filter). The module uses predefined classification services to detect inappropriate or unwanted content. Azure Content Filter sensitivity is controlled by customizable `thresholds`, assuring the content aligns with the desired standards before processing or generating as output. Llama Guard 3 Filter, equipped with 14 categories, runs on a binary mechanism, accepting only true or false. Setting a category to true enables filtering for it. It's possible to execute both filters in a single request, optimizing efficiency.

`from gen_ai_hub.orchestration_v2.models.azure_content_filter import AzureContentSafetyInput, AzureContentSafetyOutput, AzureThreshold from gen_ai_hub.orchestration_v2.models.llama_guard_3_filter import LlamaGuard38bFilter from gen_ai_hub.orchestration_v2.models.content_filtering import FilteringModuleConfig, InputFiltering, OutputFiltering from gen_ai_hub.orchestration_v2.models.content_filter import AzureContentSafetyInputFilterConfig, AzureContentSafetyOutputFilterConfig, LlamaGuard38bFilterConfig content_filter_config = FilteringModuleConfig(     input=InputFiltering(filters=[        AzureContentSafetyInputFilterConfig(config=AzureContentSafetyInput(hate=AzureThreshold.ALLOW_SAFE,                                                                                  violence=AzureThreshold.ALLOW_SAFE,                                                                                  self_harm=AzureThreshold.ALLOW_SAFE,                                                                                  sexual=AzureThreshold.ALLOW_SAFE)),        LlamaGuard38bFilterConfig(config=LlamaGuard38bFilter(hate=True))        ]),    output=OutputFiltering(filters=[        AzureContentSafetyOutputFilterConfig(config=AzureContentSafetyOutput(hate=AzureThreshold.ALLOW_SAFE,                                                                                  violence=AzureThreshold.ALLOW_SAFE,                                                                                  self_harm=AzureThreshold.ALLOW_SAFE,                                                                                  sexual=AzureThreshold.ALLOW_SAFE)),        LlamaGuard38bFilterConfig(config=LlamaGuard38bFilter(hate=True))    ]) ) template = Template(     template=[        SystemMessage(content="You are a helpful AI assistant."),        UserMessage(content="{{?text}}"),    ]    ) llm=LLMModelDetails(name="gpt-4o") prompt_template = PromptTemplatingModuleConfig(prompt=template,                                                model=llm) module_config = ModuleConfig(prompt_templating=prompt_template, filtering=content_filter_config) config = OrchestrationConfig(modules=module_config) client = OrchestrationService(config=config)`

`from gen_ai_hub.orchestration_v2.exceptions import OrchestrationError try:     result = client.run(placeholder_values={"text": "I hate you"})    print(result.final_result.choices[0].message.content) except OrchestrationError as er:     print(er.message)`

## Streaming

When you initiate an orchestration request, the full response is typically processed and delivered in one go. For longer responses, this can lead to delays in receiving the complete output. To mitigate this, you have the option to stream the results as they are being generated. This helps in rapidly processing or displaying initial portions of the results without waiting for the entire computation to finish.

To activate streaming, use the `stream` method of the `OrchestrationService` with the `stream` option in `OrchestrationConfig`. This method returns an object that streams chunks of the response as they become available. You can then extract relevant information from the `delta` field.

Here's how you can set up a simple configuration to stream orchestration results:

`from gen_ai_hub.orchestration_v2.models.streaming import GlobalStreamOptions template = Template(     template=[        SystemMessage(content="You are a helpful AI assistant."),        UserMessage(content="{{?text}}"),    ]    ) llm=LLMModelDetails(         name="gpt-4o-mini",        params={            "max_completion_tokens": 256,            "temperature": 0.0        }    ) prompt_template = PromptTemplatingModuleConfig(prompt=template,                                                model=llm) module_config = ModuleConfig(prompt_templating=prompt_template) config = OrchestrationConfig(modules=module_config,                              stream=GlobalStreamOptions(enabled=True)) client = OrchestrationService(config=config) result = client.stream(placeholder_values={     "text": "Which color is the sky? Answer in one sentence." }) for part in result:     print(part.final_result.choices[0].delta.content)    print("*" * 20)`

**Note:** As shown above, streaming responses contain a delta field instead of a message field.

You can customize the global stream behavior by setting options like `chunk_size` which controls the amount of data processed in each chunk:

`config = OrchestrationConfig(modules=module_config,                              stream=GlobalStreamOptions(enabled=True, chunk_size=25)) client = OrchestrationService(config=config) result = client.stream(placeholder_values={     "text": "Which color is the sky? Answer in one sentence." }) for part in result:     print(part.final_result.choices[0].delta.content)    print("*" * 20)`

Modules that influence or process streaming results, such as `OutputFiltering`, might need specific stream options. The `overlap` option allows you to include extra context during the filtering process:

`from gen_ai_hub.orchestration_v2.models.content_filter import FilteringStreamOptions content_filter_config = FilteringModuleConfig(     output=OutputFiltering(        filters=[AzureContentSafetyOutputFilterConfig(config=AzureContentSafetyOutput(hate=0))],        stream_options=FilteringStreamOptions(overlap=20)) ) template = Template(     template=[        SystemMessage(content="You are a helpful AI assistant."),        UserMessage(content="{{?text}}"),    ]    ) llm=LLMModelDetails(name="gpt-4o") prompt_template = PromptTemplatingModuleConfig(prompt=template,                                                model=llm) module_config = ModuleConfig(prompt_templating=prompt_template, filtering=content_filter_config) config = OrchestrationConfig(modules=module_config,                              stream=GlobalStreamOptions(enabled=True)) client = OrchestrationService(config=config) response = client.stream(placeholder_values={"text": "Which color is the sky? Answer in one sentence."}) for chunk in response:     print(chunk.final_result.choices[0].delta.content, end='')`

## Tool Calling (Function Calling)

The Orchestration Service supports **tool calling**, which allows large language models (LLMs) to request the execution of external operations such as Python functions, API calls, or other tools as part of their workflow.

This feature enables you to build advanced AI solutions that can perform calculations, access data, or interact with external systems in response to user input.

---

### Defining Tools

You can define tools in several ways, depending on your requirements and the level of control you need.

#### Using the Python Decorator

The simplest way to define a tool is to decorate a Python function with `@function_tool()`. The function’s signature and docstring are used to describe the tool to the LLM.

`from gen_ai_hub.orchestration_v2.models.tools import function_tool @function_tool() def multiply(a: int, b: int) -> int:     """Multiply two numbers."""    return a * b @function_tool() def add(a: int, b: int) -> int:     """Add two numbers."""    return a + b tools = [multiply, add]`

#### Using the `FunctionTool` Class

For more control, you can use the `FunctionTool` class directly. This is useful if you want to customize the schema, enable strict argument checking, or wrap an existing function.

`from gen_ai_hub.orchestration_v2.models.tools import FunctionTool, FunctionObject def get_weather(location: str) -> str:     """Get current temperature for a given location."""    # Replace with your actual implementation    return "22°C" weather_tool_func = FunctionObject(     name="get_weather",    description="Get current temperature for a given location.",    parameters={        "type": "object",        "properties": {            "location": {                "type": "string",                "description": "City and country e.g. Bogotá, Colombia"            }        },        "required": ["location"],        "additionalProperties": False    },    strict=True,    function=get_weather ) weather_tool = FunctionTool(function=weather_tool_func) tools = [weather_tool]`

You can also create a `FunctionTool` from a function using the `from_function` static method:

`weather_tool = FunctionTool.from_function(get_weather, strict=True) tools = [weather_tool]`

#### Using a JSON Schema Dictionary

You can define a tool directly as a JSON schema dictionary. This is useful if you want to specify the tool interface without implementing the function in Python, or if you want to integrate with external systems.

`tools = [{     "type": "function",    "function": {        "name": "get_weather",        "description": "Get current temperature for a given location.",        "parameters": {            "type": "object",            "properties": {                "location": {                    "type": "string",                    "description": "City and country e.g. Bogotá, Colombia"                }            },            "required": [                "location"            ],            "additionalProperties": False        },        "strict": True    } }]`

You can then attach any of these tool definitions to your template:

`from gen_ai_hub.orchestration_v2.models.template import Template from gen_ai_hub.orchestration_v2.models.message import SystemMessage, UserMessage template = Template(     template=[        SystemMessage(content="You are a weather assistant."),        UserMessage(content="What is the temperature in {{?location}}?"),    ],    tools=tools, )`

### Synchronous Tool Call Workflow

When the LLM decides to call a tool, the orchestration response will include a `tool_calls` field. You are responsible for executing the tool(s), adding the results to the conversation history, and running the orchestration again to get the final answer.

`from typing import List from gen_ai_hub.orchestration_v2.models.message import ChatMessage, SystemMessage, UserMessage, ToolChatMessage # Assume 'template' and 'weather_tool' are defined as above llm = LLMModelDetails(name="gpt-4o-mini", params={"max_completion_tokens": 200, "temperature": 0.0}) rompt_template = PromptTemplatingModuleConfig(prompt=template,                                                model=llm) module_config = ModuleConfig(prompt_templating=prompt_template) config = OrchestrationConfig(modules=module_config) client = OrchestrationService(config=config) template_values = {"location": "Bogotá, Colombia"} # First run: triggers tool call service = OrchestrationService() response = service.run(config=config, placeholder_values=template_values) tool_calls = response.final_result.choices[0].message.tool_calls # Execute tool(s) and build new history history: List[ChatMessage] = [] history.extend(response.intermediate_results.templating) history.append(response.final_result.choices[0].message) for tool_call in tool_calls:     # For FunctionTool, use .execute(**tool_call.function.parse_arguments())    result = weather_tool.execute(**tool_call.function.parse_arguments())    tool_message = ToolChatMessage(        content=str(result),        tool_call_id=tool_call.id,    )    history.append(tool_message) # Second run: LLM receives tool result and produces final answer response2 = service.run(     config=config,    placeholder_values=template_values,    history=history, ) print(response2.final_result.choices[0].message.content)`

### Streaming Tool Calls

When using streaming, tool calls may be split across multiple chunks. The `delta.tool_calls` field in each chunk contains partial or complete tool call information. You may need to buffer and concatenate arguments if they arrive in pieces.

`# Assume 'config' and 'service' are defined as above config = OrchestrationConfig(modules=module_config, stream=GlobalStreamOptions(enabled=True)) service = OrchestrationService() stream = service.stream(config=config, placeholder_values=template_values) final_tool_calls = {} for chunk in stream:     for tool_call in chunk.final_result.choices[0].delta.tool_calls or []:        index = tool_call.index        if index not in final_tool_calls:            final_tool_calls[index] = tool_call        else:            # Concatenate arguments if split across chunks            final_tool_calls[index].function.arguments += tool_call.function.arguments # Now final_tool_calls contains all tool calls with complete arguments`

**⚠️ Note on Agentic Loop Support:**

> The current SDK **does not provide built-in abstractions or convenience methods for managing the agentic loop** (the process of automatically handling tool call detection, execution, and iterative orchestration until a final answer is produced).
> 
> As a user, you are responsible for:
> 
> -   Detecting tool calls in the LLM response
>     
> -   Executing the corresponding Python functions
>     
> -   Appending tool results to the conversation history (as `ToolMessage`)
>     
> -   Re-invoking the orchestration service as needed
>     
> 
> This approach gives you maximum flexibility, but you must implement the orchestration loop logic yourself.

## Using Images as Input

The Orchestration Service supports multimodal prompts, enabling you to include images alongside text in your messages. This powerful feature unlocks a variety of applications, such as visual question answering (VQA), image captioning, object recognition, and generating text creatively based on visual input.

This guide details how to prepare image inputs, integrate them into your prompts, and execute the orchestration to get insightful responses.

### 1\. Preparing Image Inputs

To use an image, you first need to represent it as an `ImageItem` object. The `gen_ai_hub.orchestration.models.multimodal_items.ImageItem` class provides two convenient ways to do this:

#### a) From a URL or Data URL

This method is ideal for images hosted online or when you have the image data encoded as a Data URL (base64 encoded).

-   **Standard URL:** Provide a direct web link to the image file.
    
-   **Data URL:** Provide the image data directly embedded in the URL string.
    

**Note:** For web URLs, ensure the image is publicly accessible, as the service will need to fetch it.

`from gen_ai_hub.orchestration_v2.models.multimodal_items import ImageItem # Example 1: Image from a standard, publicly accessible URL # Ensure the URL points directly to the image file (e.g., .png, .jpg, ...) image_from_web = ImageItem(url="https://picsum.photos/id/1/200/300")  # example image URL # Example 2: Image from a Data URL (base64-encoded) # This is useful when you have the image content as a string. # The format is "data:[<mediatype>][;base64],<data>" image_from_data_url = ImageItem(     url="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAIAAAACUFjqAAAAE0lEQVR4nGP8z4APMOGVZRip0gBBLAETee26JgAAAABJRU5ErkJggg==" )`

#### b) From a Local File

If your image resides on your local filesystem, you can load it directly using the `ImageItem.from_file()` class method. The `from_file` method handles opening, reading, and base64 encoding the image data for you, packaging it into an `ImageItem`.

`from gen_ai_hub.orchestration_v2.models.multimodal_items import ImageItem # Example: Image from a local file path # To use this 'image_from_local_file' object, ensure it was successfully created. try:     image_from_local_file = ImageItem.from_file("path/to/your/local/image.jpeg") except FileNotFoundError:     print("Error: The specified image file was not found.") except Exception as e:     print(f"An error occurred while loading the image: {e}")`

### 2\. Adding Images to a Prompt

Once you have your `ImageItem` object(s), you can combine them with text to create a multimodal prompt. This is done by passing a list containing `ImageItem` instances and text strings to the `content` parameter of a `UserMessage`.

`from gen_ai_hub.orchestration_v2.models.message import UserMessage from gen_ai_hub.orchestration_v2.models.template import Template llm=LLMModelDetails(name="gpt-4o") # Simple visual question answering content_vqa = [image_from_web, "What objects are prominent in this image?"] # Create a UserMessage with the mixed content user_message = UserMessage(content=content_vqa) # Create a Template containing the UserMessage prompt_template = PromptTemplatingModuleConfig(prompt=template,model=llm) module_config = ModuleConfig(prompt_templating=prompt_template) config = OrchestrationConfig(modules=module_config) service = OrchestrationService(config=config) response = service.run() print(response.final_result.choices[0].message.content)`

## Translation

Translation module can be used to translate text from one language to another. You can use this module to translate input text before it is processed by the LLM module, or to translate the output generated by the LLM module. The translation module uses the SAP Document Translation service to perform the translation.

`from gen_ai_hub.orchestration_v2.models.message import SystemMessage, UserMessage from gen_ai_hub.orchestration_v2.models.template import Template, PromptTemplatingModuleConfig from gen_ai_hub.orchestration_v2.models.llm_model_details import LLMModelDetails from gen_ai_hub.orchestration_v2.models.config import ModuleConfig, OrchestrationConfig from gen_ai_hub.orchestration_v2.service import OrchestrationService from gen_ai_hub.orchestration_v2.models.translation import TranslationModuleConfig, SAPDocumentTranslationInput, SAPDocumentTranslationOutput, InputTranslationConfig, OutputTranslationConfig translation_config = TranslationModuleConfig(     input=SAPDocumentTranslationInput(        config=InputTranslationConfig(            source_language="en-US",            target_language="de-DE"        )    ),    output=SAPDocumentTranslationOutput(        config=OutputTranslationConfig(            source_language="de-DE",            target_language="fr-FR"        )    ) ) template = Template(     template=[        SystemMessage(content="You are a helpful AI assistant."),        UserMessage(content="{{?text}}"),    ]    ) llm=LLMModelDetails(name="gpt-4o") prompt_template = PromptTemplatingModuleConfig(prompt=template,                                                model=llm) module_config = ModuleConfig(prompt_templating=prompt_template, translation=translation_config) config = OrchestrationConfig(modules=module_config) orchestration_service = OrchestrationService()`

`result = orchestration_service.run(     config=config,    placeholder_values={"text": "What is the capital of Germany?"} )`

`print(result.final_result.choices[0].message.content)`

## Advanced Examples

`service = OrchestrationService(api_url=YOUR_API_URL)`

### Translation Service

This example extends the initial walkthrough of a basic orchestration pipeline by abstracting the translation task into its own reusable `TranslationService` class. Once the configuration is established, it can be easily adapted and reused for different translation scenarios.

`from gen_ai_hub.orchestration_v2.models.config import OrchestrationConfig, ModuleConfig from gen_ai_hub.orchestration_v2.models.llm_model_details import LLMModelDetails from gen_ai_hub.orchestration_v2.models.message import SystemMessage, UserMessage from gen_ai_hub.orchestration_v2.models.template import Template, PromptTemplatingModuleConfig from gen_ai_hub.orchestration_v2.service import OrchestrationService class TranslationService:     def __init__(self, orchestration_service: OrchestrationService):        self.service = orchestration_service        self.template = Template(                template=[                    SystemMessage(content="You are a helpful AI assistant."),                    UserMessage(content="Translate the following text to {{?to_lang}}: {{?text}}"),                ],                defaults={"to_lang": "en-US"}                )         self.llm=LLMModelDetails(name="gpt-4o")         self.prompt_template = PromptTemplatingModuleConfig(prompt=self.template, model=self.llm)         self.module_config = ModuleConfig(prompt_templating=self.prompt_template)         self.config = OrchestrationConfig(modules=self.module_config)     def translate(self, text, to_lang):        response = self.service.run(            config=self.config,            placeholder_values={                "to_lang": to_lang,                "text": text            },        )         return response.final_result.choices[0].message.content`

`translator = TranslationService(orchestration_service=service)`

`result = translator.translate(text="Hello, world!", to_lang="French") print(result)`

`result = translator.translate(text="Hello, world!", to_lang="Spanish") print(result)`

`result = translator.translate(text="Hello, world!", to_lang="German") print(result)`

### Chatbot with Memory

This example demonstrates how to integrate the `OrchestrationService` with a chatbot to handle conversational flow.

When making requests to the orchestration service, you can specify a list of messages as `history` that will be prepended to the templated content and processed by the templating module. These messages are plain, non-templated messages, as they typically represent past conversation outputs — such as in this chatbot scenario.

It’s important to note that managing conversation history / state is handled locally in the `ChatBot` class, not by the orchestration service itself.

`from typing import List from gen_ai_hub.orchestration_v2.models.config import OrchestrationConfig, ModuleConfig from gen_ai_hub.orchestration_v2.models.llm_model_details import LLMModelDetails from gen_ai_hub.orchestration_v2.models.message import ChatMessage, SystemMessage, UserMessage from gen_ai_hub.orchestration_v2.models.template import Template, PromptTemplatingModuleConfig from gen_ai_hub.orchestration_v2.service import OrchestrationService class ChatBot:     def __init__(self, orchestration_service: OrchestrationService):        self.service = orchestration_service        self.template = Template(            template=[                SystemMessage(content="You are a helpful chatbot assistant."),                UserMessage(content="{{?user_query}}")            ]        )         self.llm = LLMModelDetails(name="gpt-4o")         self.prompt_template = PromptTemplatingModuleConfig(prompt=self.template, model=self.llm)         self.module_config = ModuleConfig(prompt_templating=self.prompt_template)         self.config = OrchestrationConfig(modules=self.module_config)         self.history: List[ChatMessage] = []     def chat(self, user_input):        response = self.service.run(            config=self.config,            placeholder_values={"user_query": user_input},            history=self.history,        )         message = response.final_result.choices[0].message         self.history = response.intermediate_results.templating        self.history.append(message)         return message.content     def reset(self):        self.history = []`

`bot = ChatBot(orchestration_service=OrchestrationService())`

`print(bot.chat("Hello, how are you?"))`

`print(bot.chat("What's the weather like today?"))`

`print(bot.chat("Can you remember what I first asked you?"))`

`bot.reset()`

`print(bot.chat("Can you remember what I first asked you?"))`

### Sentiment Analysis with Few Shot Learning

This example demonstrates the different message `roles` in the templating module through a few-shot learning use case with the `FewShotLearner` class.

-   **Message Types:** Different message types (`SystemMessage`, `UserMessage`, `AssistantMessage`) structure the interaction and guide the model's behavior.
    
-   **Templating:** The template includes these examples, ending with a `placeholder` ({{?user\_input}}) for dynamic user input.
    
-   **Few-Shot Examples:** Pairs of UserMessage and AssistantMessage show how the model should respond to similar queries.
    

The FewShotLearner class manages the dynamic creation of the template and ensures the correct message roles are used for each user input.

`from typing import List, Tuple from gen_ai_hub.orchestration_v2.models.config import OrchestrationConfig,ModuleConfig from gen_ai_hub.orchestration_v2.models.llm_model_details import LLMModelDetails from gen_ai_hub.orchestration_v2.models.message import (     SystemMessage,    UserMessage,    AssistantMessage, ) from gen_ai_hub.orchestration_v2.models.template import Template, PromptTemplatingModuleConfig from gen_ai_hub.orchestration_v2.service import OrchestrationService class FewShotLearner:     def __init__(            self,            orchestration_service: OrchestrationService,            system_message: SystemMessage,            examples: List[Tuple[UserMessage, AssistantMessage]],    ):        self.service = orchestration_service         self.llm = LLMModelDetails(name="gpt-4o-mini")         self.prompt_template = PromptTemplatingModuleConfig(            prompt=self._create_few_shot_template(system_message, examples),            model=self.llm        )         self.module_config = ModuleConfig(prompt_templating=self.prompt_template)         self.config = OrchestrationConfig(modules=self.module_config)     @staticmethod    def _create_few_shot_template(            system_message: SystemMessage,            examples: List[Tuple[UserMessage, AssistantMessage]],    ) -> Template:        messages = [system_message]         for example in examples:            messages.append(example[0])            messages.append(example[1])        messages.append(UserMessage(content="{{?user_input}}"))         return Template(template=messages)     def predict(self, user_input: str) -> str:        response = self.service.run(            config=self.config,            placeholder_values={"user_input": user_input},        )         return response.final_result.choices[0].message.content`

`sentiment_examples = [     (UserMessage(content="I love this product!"), AssistantMessage(content="Positive")),    (UserMessage(content="This is terrible service."), AssistantMessage(content="Negative")),    (UserMessage(content="The weather is okay today."), AssistantMessage(content="Neutral")), ]`

`sentiment_analyzer = FewShotLearner(     orchestration_service=OrchestrationService(),    system_message=SystemMessage(        content="You are a sentiment analysis assistant. Classify the sentiment as Positive, Negative, or Neutral."    ),    examples=sentiment_examples, )`

`print(sentiment_analyzer.predict("The movie was a complete waste of time!"))`

`print(     sentiment_analyzer.predict("The traffic was fortunately unusually light today.") )`

`print(     sentiment_analyzer.predict("I'm not sure how I feel about the recent events.") )`

## Async Support

The `OrchestrationService` also supports asynchronous calls. Use:

-   `arun` from the async version of `run`
    
-   `astream` from the async version of `stream`
    

`from gen_ai_hub.orchestration_v2.models.message import SystemMessage, UserMessage from gen_ai_hub.orchestration_v2.models.template import Template, PromptTemplatingModuleConfig from gen_ai_hub.orchestration_v2.models.llm_model_details import LLMModelDetails from gen_ai_hub.orchestration_v2.models.config import OrchestrationConfig, ModuleConfig from IPython.display import display, Markdown # just for pretty print in jupyter template = Template(     template=[        SystemMessage(content="This is a system message."),        UserMessage(content="Write a markdown cheatsheet!"),    ]    ) llm=LLMModelDetails(name="gemini-2.0-flash") prompt_template = PromptTemplatingModuleConfig(prompt=template,                                                model=llm) module_config = ModuleConfig(prompt_templating=prompt_template) config = OrchestrationConfig(modules=module_config) # Instantiate the orchestration service. from gen_ai_hub.orchestration_v2.service import OrchestrationService orchestration_service = OrchestrationService(config=config)`

`async def test_async():     async_result = await orchestration_service.arun()    display(Markdown(async_result.final_result.choices[0].message.content)) await test_async()`

`from gen_ai_hub.orchestration_v2.models.streaming import GlobalStreamOptions config_stream = OrchestrationConfig(modules=module_config,stream=GlobalStreamOptions(enabled=True)) async def test_streaming_async():     streamed_content = ""    async for chunk in await orchestration_service.astream(config=config_stream):        streamed_content += chunk.final_result.choices[0].delta.content    display(Markdown(streamed_content)) await test_streaming_async()`

## Embeddings

The Orchestration Service provides an embeddings endpoint for generating vector representations of text. Embeddings capture the semantic meaning of text, enabling powerful applications like semantic search, document clustering, and retrieval-augmented generation (RAG).

**Key Use Cases:**

-   **Semantic Search**: Find documents based on meaning, not just keywords
    
-   **RAG (Retrieval-Augmented Generation)**: Retrieve relevant context for LLM prompts
    
-   **Document Clustering**: Group similar documents together
    
-   **Similarity Comparison**: Measure how semantically similar two texts are
    

### Basic Usage

Generate an embedding for a single text string with minimal configuration.

`from gen_ai_hub.orchestration_v2.service import OrchestrationService from gen_ai_hub.orchestration_v2.models.embeddings import (     EmbeddingsOrchestrationConfig,    EmbeddingsModuleConfigs,    EmbeddingsModelConfig,    EmbeddingsModelDetails,    EmbeddingsInput, ) service = OrchestrationService() # Minimal configuration - just specify the model embeddings_config = EmbeddingsOrchestrationConfig(     modules=EmbeddingsModuleConfigs(        embeddings=EmbeddingsModelConfig(            model=EmbeddingsModelDetails(name="text-embedding-3-large")        )    ) ) response = service.embed(     config=embeddings_config,    input=EmbeddingsInput(text="Hello World!") ) embedding = response.final_result.data[0].embedding print(f"Embedding dimensions: {len(embedding)}") print(f"First 5 values: {embedding[:5]}")`

### Customizing Embedding Parameters

You can customize the embedding output with parameters like `dimensions`, `encoding_format`, and `normalize`.

Parameter

Description

Values

`dimensions`

Number of dimensions in the output

e.g. 256, 512, 1536, 3072

`encoding_format`

Output format

`FLOAT`, `BASE64`, `BINARY`

`normalize`

Normalize the vector

`True`, `False`

`from gen_ai_hub.orchestration_v2.models.embeddings import (     EmbeddingsModelParams,    EmbeddingsEncodingFormat, ) embeddings_config_custom = EmbeddingsOrchestrationConfig(     modules=EmbeddingsModuleConfigs(        embeddings=EmbeddingsModelConfig(            model=EmbeddingsModelDetails(                name="text-embedding-3-large",                params=EmbeddingsModelParams(                    dimensions=256,  # Reduce dimensions for efficiency                    encoding_format=EmbeddingsEncodingFormat.FLOAT,                    normalize=True                )            )        )    ) ) response = service.embed(     config=embeddings_config_custom,    input=EmbeddingsInput(text="Hello World!") ) print(f"Embedding dimensions: {len(response.final_result.data[0].embedding)}")`

### Batch Embeddings

Generate embeddings for multiple texts in a single request for better efficiency.

`documents = [     "Artificial intelligence is transforming industries worldwide.",    "Machine learning models require large amounts of training data.",    "Neural networks are inspired by the human brain structure.",    "Deep learning has achieved breakthroughs in image recognition." ] response = service.embed(     config=embeddings_config,    input=EmbeddingsInput(text=documents) ) print(f"Generated {len(response.final_result.data)} embeddings") for result in response.final_result.data:     print(f"  Index {result.index}: {len(result.embedding)} dimensions")`

### Input Type Hints (Asymmetric Search)

Some embedding models support asymmetric search, where queries and documents are embedded differently for better retrieval. Use the `type` parameter to hint the purpose of your text.

Type

Use Case

`TEXT`

General purpose (default)

`DOCUMENT`

Content to be indexed and searched

`QUERY`

Search queries to find relevant documents

`from gen_ai_hub.orchestration_v2.models.embeddings import EmbeddingsInputType # Embed a document for storage in a vector database doc_response = service.embed(     config=embeddings_config,    input=EmbeddingsInput(        text="SAP is a German multinational software company that develops enterprise software.",        type=EmbeddingsInputType.DOCUMENT    ) ) # Embed a query for searching query_response = service.embed(     config=embeddings_config,    input=EmbeddingsInput(        text="What is SAP?",        type=EmbeddingsInputType.QUERY    ) )`

### Embeddings with Data Masking

When embedding sensitive data, use the data masking module to anonymize PII before generating embeddings. This ensures sensitive information is not exposed to the embedding model.


...6484 bytes truncated...

The tool call succeeded but the output was truncated. Full output saved to: /Users/sfuser/.local/share/kilo/tool-output/tool_da4631c22001TF9cylGeJmQTty
Use the Task tool to have explore agent process this file with Grep and Read (with offset/limit). Do NOT read the full file yourself - delegate to save context.
```

---

## Assistant (Code · anthropic--claude-4.6-sonnet · 5.2s)

**Tool: webfetch**

**Input:**
```json
{
  "url": "https://help.sap.com/doc/generative-ai-hub-sdk/CLOUD/en-US/_reference/README_sphynx.html",
  "format": "markdown"
}
```

**Output:**
```
      SAP Cloud SDK for AI (Python) - generative | SAP Cloud SDK for AI (Python) - generative v6.7.0                       

[Skip to content](#content)

[SAP Cloud SDK for AI (Python) - generative v6.7.0](../index.html)

Toggle navigation menu

 ⌘ K

[SAP Cloud SDK for AI (Python) - generative v6.7.0](../index.html)

-   [Introduction](#)
-   [Examples](../examples.html)
    -   [Native Client Integrations](gen_ai_hub.html)
    -   [Langchain Integration](gen_ai_hub.html#langchain-integration)
    -   [SAP RPT-1 Models](gen_ai_hub.html#sap-rpt-1-models)
    -   [Using New Models Before Official SDK Support](gen_ai_hub.html#using-new-models-before-official-sdk-support)
    -   [Streaming](streaming.html)
    -   [Prompt Registry](prompt-registry.html)
    -   [Orchestration Service \[Deprecated\]](orchestration-service.html)
    -   [Orchestration Service V2 API](orchestration-service2.html)
    -   [Document Grounding](document-grounding.html)
    -   [Async examples](async-examples.html)
    -   [Generative AI Custom Evaluation](evaluations.html)
-   [Release Notes](RELEASE_NOTES.html)
-   [API Reference](../_api_doc/gen_ai_hub.html)
    -   [gen\_ai\_hub.document\_grounding package](../_api_doc/gen_ai_hub.document_grounding.html)
        -   [gen\_ai\_hub.document\_grounding.clients package](../_api_doc/gen_ai_hub.document_grounding.clients.html)
        -   [gen\_ai\_hub.document\_grounding.models package](../_api_doc/gen_ai_hub.document_grounding.models.html)
    -   [gen\_ai\_hub.evaluations package](../_api_doc/gen_ai_hub.evaluations.html)
        -   [gen\_ai\_hub.evaluations.exceptions package](../_api_doc/gen_ai_hub.evaluations.exceptions.html)
        -   [gen\_ai\_hub.evaluations.helpers package](../_api_doc/gen_ai_hub.evaluations.helpers.html)
        -   [gen\_ai\_hub.evaluations.models package](../_api_doc/gen_ai_hub.evaluations.models.html)
        -   [gen\_ai\_hub.evaluations.utils package](../_api_doc/gen_ai_hub.evaluations.utils.html)
    -   [gen\_ai\_hub.orchestration package](../_api_doc/gen_ai_hub.orchestration.html)
        -   [gen\_ai\_hub.orchestration.models package](../_api_doc/gen_ai_hub.orchestration.models.html)
    -   [gen\_ai\_hub.orchestration\_v2 package](../_api_doc/gen_ai_hub.orchestration_v2.html)
        -   [gen\_ai\_hub.orchestration\_v2.models package](../_api_doc/gen_ai_hub.orchestration_v2.models.html)
    -   [gen\_ai\_hub.prompt\_registry package](../_api_doc/gen_ai_hub.prompt_registry.html)
        -   [gen\_ai\_hub.prompt\_registry.models package](../_api_doc/gen_ai_hub.prompt_registry.models.html)
    -   [gen\_ai\_hub.proxy package](../_api_doc/gen_ai_hub.proxy.html)
        -   [gen\_ai\_hub.proxy.core package](../_api_doc/gen_ai_hub.proxy.core.html)
        -   [gen\_ai\_hub.proxy.gen\_ai\_hub\_proxy package](../_api_doc/gen_ai_hub.proxy.gen_ai_hub_proxy.html)
        -   [gen\_ai\_hub.proxy.langchain package](../_api_doc/gen_ai_hub.proxy.langchain.html)
        -   [gen\_ai\_hub.proxy.native package](../_api_doc/gen_ai_hub.proxy.native.html)
            -   [gen\_ai\_hub.proxy.native.amazon package](../_api_doc/gen_ai_hub.proxy.native.amazon.html)
            -   [gen\_ai\_hub.proxy.native.google\_genai package](../_api_doc/gen_ai_hub.proxy.native.google_genai.html)
            -   [gen\_ai\_hub.proxy.native.openai package](../_api_doc/gen_ai_hub.proxy.native.openai.html)
            -   [gen\_ai\_hub.proxy.native.sap package](../_api_doc/gen_ai_hub.proxy.native.sap.html)

[SAP Cloud SDK for AI (Python) - generative v6.7.0](../index.html)

/

SAP Cloud SDK for AI (Python) - generative

# SAP Cloud SDK for AI (Python) - generative

The SDK formerly known as *generative AI Hub SDK* was rebranded.

With this SDK you can leverage the power of generative models available in the generative AI Hub of SAP AI Core. This SDK provides LLM access by wrapping the native SDKs of the model providers (OpenAI, Amazon, Google), through langchain, or through the orchestration service.

## Installation

Use the package name to install the SDK with support for all models (OpenAI, Amazon, Google) including langchain support:

`pip install "sap-ai-sdk-gen[all]"`

With the name rebranding, class names have **not** changed i.e., you can continue to use existing code.

The default installation only includes OpenAI models (with langchain support):

`pip install sap-ai-sdk-gen`

You can install a subset of the extra libraries (with langchain support) by specifying them in square brackets:

`pip install "sap-ai-sdk-gen[google, amazon]"`

In the table below, you can see which models and vendor specific langchain packages are installed when using different installation parameters.

Install Parameter

OpenAI

Google

AWS

LangChain

OpenAI-LangChain

Google-LangChain

AWS-LangChain

yes

no

no

yes

yes

no

no

\[google\]

yes

yes

no

yes

yes

yes

no

\[amazon\]

yes

no

yes

yes

yes

no

yes

\[amazon, google\] / \[google, amazon\]

yes

yes

yes

yes

yes

yes

yes

\[all\]

yes

yes

yes

yes

yes

yes

yes

## Configuration

There are different ways to configure the SAP AI Core access (listed in order of precedence):

-   environment variables
    
-   (profile) configuration file
    
-   from VCAP\_SERVICES environment variable, if it exists
    

These methods automatically initialize an authenticated client. For custom authentication, you can provide a `proxy_client` parameter when instantiating SDK classes to use your own `GenAIHubProxyClient` with direct credential configuration.

We recommend setting these values as environment variables or via config file. The default path for the configuration file is `~/.aicore/config.json`

### Environment variables

-   `AICORE_CLIENT_ID`: This represents the client ID.
    
-   `AICORE_CLIENT_SECRET`: This stands for the client secret.
    
-   `AICORE_AUTH_URL`: This is the URL used to retrieve a token using the client ID and secret.
    
-   `AICORE_BASE_URL`: This is the URL of the service (with suffix /v2).
    
-   `AICORE_RESOURCE_GROUP`: This represents the resource group that should be used.
    
-   `AI_CLIENT_TYPE` (optional): Specify client type in request headers. Default is 'GenAI Hub SDK (Python)'. Note: This cannot be set in the config file.
    

For using X.509 credentials, you can set the file paths to certificate and key files, or certificate and key strings, as an alternative to client secret.

-   `AICORE_CERT_FILE_PATH`: This is the path to the file which holds the X.509 certificate
    
-   `AICORE_KEY_FILE_PATH`: This is the path to the file which holds the X.509 key
    
-   `AICORE_CERT_STR`: This is the content of the X.509 certificate as a string
    
-   `AICORE_KEY_STR`: This is the content of the X.509 key as a string
    

### Configuration files

By default, the configuration file is located at `~/.aicore/config.json`. You can change the directory where the config file is located by setting the `AICORE_HOME` environment variable.

Note: tilde (~) is not supported, so use the full path to the directory.

A profile is a json file residing in a config directory. With profile names one can switch easily between profiles e.g., for different (sub)accounts. The profile name can be passed also as a keyword. If no profile is specified, the default profile is used. Specify the profile via envionment variable `AICORE_PROFILE`. The associated configuration file then needs to have file name `config_{profile}.json`

The command `aicore configure --help` can be used to generate a profile.

The following list explains which environment variables can be used to control which configuration file will be used:

1.  **`AICORE_HOME`**: This variable represents a directory path. Within this directory, various configuration files can be stored and the SDK will automatically load them from there based on the "AICORE\_PROFILE" environment variable.
    
2.  **`AICORE_PROFILE`**: This variable allows users to switch between different configurations stored in the `AICORE_HOME` directory. It is important to note that `AICORE_PROFILE` does not represent the complete name of a configuration file. Instead, it refers to a profile name, which corresponds to a file named `config_{profile}.json`. If AICORE\_PROFILE is empty `$AICORE_HOME/config.json` is used.
    
3.  **`AICORE_CONFIG`**: This variable overrides both `AICORE_HOME` and `AICORE_PROFILE`. It specifies the direct absolute path to a configuration file that will be used.
    

The configuration file should be:

`{   "AICORE_AUTH_URL": "https://* * * .authentication.sap.hana.ondemand.com/oauth/token",  "AICORE_CLIENT_ID": "* * * ",  "AICORE_CLIENT_SECRET": "* * * ",  "AICORE_RESOURCE_GROUP": "* * * ",  "AICORE_BASE_URL": "https://api.ai.* * *.cfapps.sap.hana.ondemand.com/v2" }`

or

`{   "AICORE_AUTH_URL": "https://* * * .authentication.cert.sap.hana.ondemand.com",  "AICORE_CLIENT_ID": "* * * ",  "AICORE_CERT_FILE_PATH": "* * */cert.pem",  "AICORE_KEY_FILE_PATH": "* * */key.pem",  "AICORE_RESOURCE_GROUP": "* * * ",  "AICORE_BASE_URL": "https://api.ai.* * *.cfapps.sap.hana.ondemand.com/v2" }`

or

`{   "AICORE_AUTH_URL": "https://* * * .authentication.cert.sap.hana.ondemand.com",  "AICORE_CLIENT_ID": "* * * ",  "AICORE_CERT_STR": "* * *",  "AICORE_KEY_STR": "* * *",  "AICORE_RESOURCE_GROUP": "* * * ",  "AICORE_BASE_URL": "https://api.ai.* * *.cfapps.sap.hana.ondemand.com/v2" }`

## Usage

### Prerequisite

For direct model access, you need to create a deployment for each desired model according to according to the [help documentation for model deployments](https://help.sap.com/docs/sap-ai-core/sap-ai-core-service-guide/create-deployment-for-generative-ai-model-in-sap-ai-core).

For model access through the orchestration service, you need to create a deployment of the orchestration service according to the [help documentation for orchestration service deployments](https://help.sap.com/docs/sap-ai-core/sap-ai-core-service-guide/create-deployment-for-orchestration)

### Examples

In section "*Examples*" there are code snippets for each Large Language and Embedding model as well as for the orchestration service usage.

## Supported Models

The list of models in the Generative AI Hub of SAP AI Core can be found in [SAP note 343776](https://me.sap.com/notes/3437766). Among these, the following models are currently supported in the SAP Cloud SDK for AI (Python) - generative:

### LLM Models

Provider

Model Name

Streaming Support

Amazon

amazon--nova-lite

No

amazon--nova-micro

No

amazon--nova-pro

No

amazon--amazon--nova-premier

Yes

Anthropic

anthropic--claude-3-haiku

Yes

anthropic--claude-3.5-sonnet

Yes

anthropic--claude-3.7-sonnet

Yes

anthropic--claude-4-sonnet

Yes

anthropic--claude-4-opus

Yes

anthropic--claude-4.5-sonnet

Yes

anthropic--claude-4.5-haiku

Yes

Google

gemini-2.0-flash

Yes

gemini-2.0-flash-lite

Yes

gemini-2.5-flash

Yes

gemini-2.5-pro

Yes

gemini-2.5-flash

Yes

gemini-2.5-flash-lite

Yes

MistralAI

mistralai--mistral-small-instruct

No

mistralai--mistral-medium-instruct

No

mistralai--mistral-large-instruct

No

OpenAI

gpt-4o

Yes

gpt-4o-mini

Yes

gpt-4.1

Yes

gpt-4.1-mini

Yes

gpt-4.1-nano

Yes

gpt-5

Yes

gpt-5-mini

Yes

gpt-5-nano

Yes

o1

No

o3

Yes

o3-mini

No

o4-mini

Yes

Cohere

cohere--command-a-reasoning

Yes

cohere--reranker

Yes

Perplexity

sonar

Yes

sonar-pro

Yes

### Embedding Models

Provider

Model Name

Amazon

amazon--titan-embed-text

amazon--titan-embed-image

Google

google--gemini-embedding

NVIDIA

nvidia--llama-3.2-nv-embedqa-1b

OpenAI

text-embedding-3-small

text-embedding-3-large

text-embedding-ada-002

### Notes on model usage

-   ⚠️ **Anthropic & Amazon**:
    
    -   Currently, for `amazon--nova-lite`, `amazon--nova-micro`, and `amazon--nova-pro`, the supported method is `converse`. `invoke` and `invoke_model_with_response_stream` are not supported.
        
-   ℹ️ **MistralAI:**
    
    -   This model only supports the following roles in the order implied: user/assistant/user/assistant/....
        
-   ℹ️ **Perplexity:**
    
    -   The Perplexity Sonar models are also based on the OpenAI SDK and usage for these models is similar to that of GPT models.
        
    -   Search-API is not supported yet.
        
-   ℹ️ **Cohere:**
    
    -   The cohere--command-a-reasoning model is also based on the OpenAI SDK and usage for this model is similar to that of GPT models.
        
-   **Models not added to SDK yet**:
    
    -   You can also try using Generative AI Hub SDK for models that are already in Generative AI Hub, but not supported yet by the SDK. This can be done by additionally specifying the model initialization: see [Using New Models Before Official SDK Support](gen_ai_hub.html#unsupported-models). Please note, that it's not guaranteed that it will work. Because there might be some new models, for which customization in the SDK is needed.
        

## Package dependencies

Please note the following dependencies of sap-ai-sdk-gen:

`httpx>=0.27.0 h11>=0.16.0 dacite>=1.8.1 click>=8.1.7 overloading==0.5.0 packaging>=23.2 sap-ai-sdk-core>=3.1.0 pydantic~=2.12 openai>=1.58.1 google-genai~=1.60.0 # google boto3>=1.40.61 # amazon aiobotocore>=3.0.0 # amazon langchain~=1.2.6 langchain_google_genai~=4.2.0 # google langchain-classic~=1.0.0 langchain-community~=0.4.1 langchain-openai~=1.1.0 langchain-aws~=1.1.0 # amazon`

On this page

-   [Installation](#installation)
-   [Configuration](#configuration)
    -   [Environment variables](#environment-variables)
    -   [Configuration files](#configuration-files)
-   [Usage](#usage)
    -   [Prerequisite](#prerequisite)
    -   [Examples](#examples)
-   [Supported Models](#supported-models)
    -   [LLM Models](#llm-models)
    -   [Embedding Models](#embedding-models)
    -   [Notes on model usage](#notes-on-model-usage)
-   [Package dependencies](#package-dependencies)

© 2026, SAP SE Built with [Sphinx 8.2.3](https://www.sphinx-doc.org)

-   [Copyright](http://go.sap.com/about/legal/copyright.html)
-   [Disclaimer](/docs/disclaimer)
-   [Privacy Statement](/docs/privacy)
-   [Legal Disclosure](https://www.sap.com/about/legal/impressum.html)
-   [Trademark](https://www.sap.com/about/legal/trademark.html)
-   [Terms of Use](http://www.sap.com/corporate/en/legal/terms-of-use.html)
```

---

## Assistant (Code · anthropic--claude-4.6-sonnet · 26.1s)

Now I have a comprehensive picture. Here is the full investigation result:

---

## SAP Orchestration API — Deployment-Less Model Access

### What Changed

SAP has introduced two new approaches that **remove the need for per-model deployments**:

1. **Orchestration Service V2** (`gen_ai_hub.orchestration_v2`) — the current recommended API
2. **Orchestration Service V1** (`gen_ai_hub.orchestration`) — **deprecated** as of 2025

The old pattern required you to deploy each model individually via `POST /v2/lm/deployments` and then route to `{deployment_url}/...`. The new orchestration service uses **a single "orchestration service deployment"** — you only deploy the orchestration service once, and then access any model by name in the request body.

---

### How to Discover Available Models

**Option 1: REST API** — `GET /v2/lm/foundation-models`

```
GET {AI_API_URL}/v2/lm/foundation-models
Headers:
  Authorization: Bearer <token>
  AI-Resource-Group: <resource_group>
```

This returns all available foundation models in your subaccount without requiring any model-specific deployments.

**Option 2: SDK Documentation** — the full model list is maintained at [SAP Note 3437766](https://me.sap.com/notes/3437766). As of April 2026, confirmed available models via SDK v6.7.0 include:

| Provider | Model Name |
|---|---|
| OpenAI | `gpt-4o`, `gpt-4o-mini`, `gpt-4.1`, `gpt-4.1-mini`, `gpt-5`, `gpt-5-nano`, `o3`, `o4-mini` |
| Anthropic | `anthropic--claude-3.7-sonnet`, `anthropic--claude-4-sonnet`, `anthropic--claude-4.5-sonnet` |
| Google | `gemini-2.0-flash`, `gemini-2.5-pro`, `gemini-2.5-flash` |
| MistralAI | `mistralai--mistral-large-instruct` |
| Amazon | `amazon--nova-pro`, `amazon--nova-lite`, `amazon--nova-micro` |
| Cohere | `cohere--command-a-reasoning` |
| Perplexity | `sonar`, `sonar-pro` |

---

### How to Access Models (Orchestration V2)

#### 1. Prerequisites

Deploy the orchestration service **once** per resource group (not per model):

```
POST /v2/lm/deployments
{
  "configurationId": "<orchestration-service-config-id>"
}
```

Once deployed, a single orchestration deployment URL handles all models.

#### 2. Call any model by name in the request

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

#### 3. Raw HTTP call (no SDK)

The underlying REST endpoint the SDK calls is:

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
        "model_params": {"max_tokens": 512}
      },
      "templating_module_config": {
        "template": [
          {"role": "system", "content": "You are a helpful assistant."},
          {"role": "user", "content": "{{?user_query}}"}
        ]
      }
    }
  },
  "input_params": {"user_query": "Hello!"}
}
```

---

### Impact on This Proxy Codebase

The current proxy (`sap-ai-core-llm-proxy`) is built on the **old model**:
- Discovers/caches `{AI_API_URL}/v2/lm/deployments` per model at startup
- Routes each request to `{deployment_url}/{model-specific-endpoint}`

The new orchestration V2 approach would require a fundamentally different architecture:
- **Model discovery**: call `GET /v2/lm/foundation-models` instead of listing deployments
- **Single endpoint**: route all completions to `{orchestration_deployment_url}/completion` with `model_name` in the body
- **No deployment auto-discovery needed**: the model name in the request body is sufficient

There is an **unmerged branch** `feat/sap-ai-orchestration-model-discovery` (found in `.git/FETCH_HEAD`) that was started for this work but never merged into `main`.

---

## User

export as md

---

## Assistant (Code · anthropic--claude-4.6-sonnet)

**Tool: write**

**Input:**
```json
{}
```

---

