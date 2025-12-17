#!/usr/bin/env python3
"""
Test script to verify the retry logic with 4 attempts using mixed strategy (2 regular + 2 exponential).
"""

import time
from tenacity import retry, stop_after_attempt, wait_fixed, wait_exponential, wait_chain
from botocore.exceptions import ClientError


def retry_on_rate_limit(exception):
    """Check if exception is a rate limit error that should be retried."""
    error_message = str(exception).lower()
    return (
        "too many tokens" in error_message
        or "rate limit" in error_message
        or "throttling" in error_message
        or "too many requests" in error_message
        or "exceeding the allowed request" in error_message
        or "rate limited by ai core" in error_message
    )


# Create a mixed retry strategy: 2 fixed wait attempts + 2 exponential wait attempts
# This gives us: 0.1s (fixed) + 0.2s (fixed) + 0.3s (exp) + 0.6s (exp) = 1.2s total max
bedrock_retry = retry(
    stop=stop_after_attempt(5),  # 1 original + 4 retries = 5 total attempts
    wait=wait_chain(
        wait_fixed(0.1),  # First retry: 0.1s fixed wait
        wait_fixed(0.2),  # Second retry: 0.2s fixed wait
        wait_exponential(multiplier=0.1, min=0.3, max=0.6)  # Remaining retries: exponential
    ),
    retry=retry_on_rate_limit,
    before_sleep=lambda retry_state: print(
        f"Rate limit hit, retrying in {retry_state.next_action.sleep if retry_state.next_action else 'unknown'} seconds "
        f"(attempt {retry_state.attempt_number}/5): {str(retry_state.outcome.exception()) if retry_state.outcome else 'unknown error'}"
    ),
)


class MockBedrockClient:
    def __init__(self, fail_count=3):
        self.call_count = 0
        self.fail_count = fail_count

    @bedrock_retry
    def invoke_model(self, body=None):
        self.call_count += 1
        if self.call_count <= self.fail_count:
            # Simulate the ClientError from SAP AI Core rate limiting
            raise ClientError(
                error_response={
                    "Error": {
                        "Code": "429",
                        "Message": "Your request has been rate limited by AI Core due to exceeding the allowed request. Please try again later.",
                    },
                    "ResponseMetadata": {"HTTPStatusCode": 429},
                },
                operation_name="InvokeModel",
            )
        return {"body": ["success"], "ResponseMetadata": {"HTTPStatusCode": 200}}


def test_conservative_retry():
    print(
        "Testing retry logic with mixed strategy (4 retries: 2 fixed + 2 exponential)..."
    )

    # Test with 3 failures, should succeed on 4th attempt
    print("\n1. Testing with 3 failures (should succeed on 4th attempt):")
    print("Expected wait pattern: 0.1s (fixed) + 0.2s (fixed) + 0.3s (exp) = 0.6s total")
    client = MockBedrockClient(fail_count=3)
    start_time = time.time()
    try:
        result = client.invoke_model(body="test")
        elapsed = time.time() - start_time
        print(
            f"✅ Succeeded after {elapsed:.2f} seconds with {client.call_count} calls"
        )
        print(f"Final result: {result}")
    except Exception as e:
        print(f"❌ Test failed: {e}")

    # Test with 4 failures, should fail after 5 attempts
    print("\n2. Testing with 4 failures (should fail after 5 attempts):")
    print("Expected wait pattern: 0.1s + 0.2s + 0.3s + 0.6s = 1.2s total")
    client2 = MockBedrockClient(fail_count=10)  # More failures than retries
    start_time = time.time()
    try:
        result = client2.invoke_model(body="test")
        print(f"❌ Unexpected success: {result}")
    except Exception as e:
        elapsed = time.time() - start_time
        print(
            f"✅ Correctly failed after {elapsed:.2f} seconds with {client2.call_count} attempts"
        )
        print(f"Error: {type(e).__name__}")


if __name__ == "__main__":
    test_conservative_retry()
