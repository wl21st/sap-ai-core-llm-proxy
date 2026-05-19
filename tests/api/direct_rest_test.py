#!/usr/bin/env python3
"""
Direct REST API test using config.json and deployment URLs.

Usage:
  python tests/api/direct_rest_test.py [--model MODEL] [--verbose]

This script:
1. Loads config.json from current folder
2. Reads account key from service_key_json path
3. Expands deployment URLs
4. Makes direct REST POST requests to test the API
"""

import json
import sys
import argparse
import requests
from pathlib import Path
from typing import Optional, Dict, Any


def load_config(config_path: str = "config.json") -> Dict[str, Any]:
    """Load proxy config from file."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path) as f:
        config = json.load(f)

    print(f"✓ Loaded config from {config_path}")
    return config


def load_service_key(service_key_path: str) -> Dict[str, Any]:
    """Load SAP AI Core service key."""
    path = Path(service_key_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Service key not found: {service_key_path}")

    with open(path) as f:
        key = json.load(f)

    print(f"✓ Loaded service key from {service_key_path}")
    return key


def get_oauth_token(service_key: Dict[str, Any]) -> str:
    """Get OAuth token from SAP AI Core service key."""
    try:
        from gen_ai_hub.core.iam.token_helper import get_token_from_service_key
        token = get_token_from_service_key(service_key)
        print("✓ Obtained OAuth token from SAP AI Core")
        return token
    except Exception as e:
        print(f"✗ Failed to get OAuth token: {e}")
        raise


def test_model(
    config: Dict[str, Any],
    model: str,
    verbose: bool = False,
) -> bool:
    """Test a model via direct REST API POST call."""

    # Get first subaccount
    subaccount_name = next(iter(config["subAccounts"].keys()))
    subaccount = config["subAccounts"][subaccount_name]

    # Get service key
    service_key_path = subaccount["service_key_json"]
    service_key = load_service_key(service_key_path)

    # Get deployment URL for model
    deployment_urls = subaccount["model_to_deployment_urls"].get(model, [])
    if not deployment_urls:
        print(f"✗ Model {model} not configured in subaccount {subaccount_name}")
        return False

    deployment_url = deployment_urls[0]
    print(f"\nTesting model: {model}")
    print(f"  Subaccount: {subaccount_name}")
    print(f"  Deployment URL: {deployment_url}")

    # Get OAuth token
    try:
        token = get_oauth_token(service_key)
    except Exception as e:
        print(f"✗ Failed to get OAuth token: {e}")
        return False

    # Prepare POST request
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Build API endpoint URL - determine based on model type
    if "claude" in model.lower():
        # AWS Bedrock Converse API
        api_endpoint = f"{deployment_url}/converse"
        request_body = {
            "messages": [
                {
                    "role": "user",
                    "content": "Say 'Hello from SAP AI Core Bedrock proxy test'",
                }
            ],
            "max_tokens": 100,
        }
    elif "gemini" in model.lower():
        # Google Vertex Gemini API
        api_endpoint = f"{deployment_url}/generateContent"
        request_body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": "Say 'Hello from SAP AI Core Gemini proxy test'"}
                    ],
                }
            ],
        }
    else:
        # OpenAI-compatible endpoint
        api_endpoint = f"{deployment_url}/chat/completions"
        request_body = {
            "messages": [
                {
                    "role": "user",
                    "content": "Say 'Hello from SAP AI Core proxy test'",
                }
            ],
            "max_tokens": 100,
        }

    if verbose:
        print(f"  Endpoint: {api_endpoint}")
        print(f"  Request: {json.dumps(request_body, indent=2)}")

    # Make POST request
    try:
        response = requests.post(
            api_endpoint,
            headers=headers,
            json=request_body,
            timeout=30,
        )

        if response.status_code == 200:
            resp_data = response.json()
            if verbose:
                print(f"  Response: {json.dumps(resp_data, indent=2)}")
            print(f"✓ Success! Received response from {model}")
            return True
        else:
            print(f"✗ API returned status {response.status_code}")
            if verbose:
                print(f"  Response: {response.text}")
            return False

    except requests.exceptions.Timeout:
        print(f"✗ Request timeout")
        return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Request failed: {e}")
        return False
    except Exception as e:
        print(f"✗ API call failed: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Direct REST API test using config.json and deployment URLs"
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to config.json (default: config.json)",
    )
    parser.add_argument(
        "--model",
        help="Specific model to test (if not provided, tests all configured models)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    # Load config
    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        print(f"✗ {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"✗ Invalid JSON in config: {e}")
        sys.exit(1)

    # Get list of models to test
    subaccount_name = next(iter(config["subAccounts"].keys()))
    subaccount = config["subAccounts"][subaccount_name]
    all_models = list(subaccount["model_to_deployment_urls"].keys())

    if args.model:
        if args.model not in all_models:
            print(f"✗ Model {args.model} not configured")
            print(f"  Available models: {', '.join(all_models)}")
            sys.exit(1)
        models_to_test = [args.model]
    else:
        models_to_test = all_models

    print(f"SAP AI Core LLM Proxy Direct REST API Test")
    print(f"==========================================")
    print(f"Config: {args.config}")
    print(f"Subaccount: {subaccount_name}")
    print(f"Models to test: {', '.join(models_to_test)}")

    # Run tests
    results = {}
    for model in models_to_test:
        try:
            success = test_model(config, model, verbose=args.verbose)
            results[model] = success
        except Exception as e:
            print(f"✗ Unexpected error testing {model}: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            results[model] = False

    # Summary
    print(f"\n{'='*40}")
    print("Test Summary:")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"  Passed: {passed}/{total}")

    for model, success in results.items():
        status = "✓" if success else "✗"
        print(f"  {status} {model}")

    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
