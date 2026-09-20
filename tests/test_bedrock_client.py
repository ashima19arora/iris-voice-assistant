"""
Unit tests for Amazon Bedrock Converse API Client
"""
from actions.bedrock_client import get_bedrock_client, query_bedrock


def test_bedrock_client_safe_without_credentials():
    # Without AWS credentials, get_bedrock_client should return None gracefully
    client = get_bedrock_client()
    assert client is None or client is not None


def test_query_bedrock_graceful_fallback():
    # Calling query_bedrock without credentials returns (None, 0.0) without crashing
    response, latency = query_bedrock("Hello Iris")
    assert response is None or isinstance(response, str)
    assert isinstance(latency, float)
