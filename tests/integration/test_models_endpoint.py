"""
Integration tests for /v1/models endpoint.

Tests the model listing endpoint against a running proxy server.
"""

import pytest
from .test_validators import ResponseValidator


@pytest.mark.integration
@pytest.mark.real
class TestModelsEndpoint:
    """Tests for /v1/models endpoint."""

    def test_list_models_returns_200(self, proxy_client, proxy_url):
        """Test that /v1/models returns 200 OK."""
        response = proxy_client.get(f"{proxy_url}/v1/models")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    def test_list_models_response_format(self, proxy_client, proxy_url):
        """Test that /v1/models returns OpenAI-compatible format."""
        response = proxy_client.get(f"{proxy_url}/v1/models")
        assert response.status_code == 200

        data = response.json()
        assert "object" in data, "Response missing 'object' field"
        assert data["object"] == "list", f"Expected object='list', got '{data['object']}'"
        assert "data" in data, "Response missing 'data' field"
        assert isinstance(data["data"], list), "data must be a list"

    def test_list_models_contains_required_models(
        self, proxy_client, proxy_url, models_to_test
    ):
        """Test that all required models are listed."""
        response = proxy_client.get(f"{proxy_url}/v1/models")
        assert response.status_code == 200

        data = response.json()
        model_ids = [model["id"] for model in data["data"]]

        for required_model in models_to_test:
            assert (
                required_model in model_ids
            ), f"Required model '{required_model}' not found in models list. Available: {model_ids}"

    def test_model_metadata(self, proxy_client, proxy_url):
        """Test that each model has required metadata fields."""
        response = proxy_client.get(f"{proxy_url}/v1/models")
        assert response.status_code == 200

        data = response.json()
        assert len(data["data"]) > 0, "No models returned"

        for model in data["data"]:
            assert "id" in model, "Model missing 'id' field"
            assert "object" in model, "Model missing 'object' field"
            assert "created" in model, "Model missing 'created' field"
            assert "owned_by" in model, "Model missing 'owned_by' field"

            assert model["object"] == "model", f"Expected object='model', got '{model['object']}'"
            assert isinstance(model["id"], str), "Model id must be string"
            assert len(model["id"]) > 0, "Model id must not be empty"
            assert isinstance(model["created"], int), "Model created must be integer"
            assert isinstance(model["owned_by"], str), "Model owned_by must be string"

    @pytest.mark.smoke
    def test_models_endpoint_smoke(self, proxy_client, proxy_url):
        """Quick smoke test for /v1/models endpoint."""
        response = proxy_client.get(f"{proxy_url}/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) > 0, "No models available"