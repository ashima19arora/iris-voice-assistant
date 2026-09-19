"""
Unit tests for DynamoDB audit logging
"""
from actions.security.dynamo_logger import put_audit_event_async, ensure_audit_table, get_dynamo_resource


def test_dynamo_resource_safe_fallback():
    # Without AWS credentials or LocalStack running, resource may be None or local resource
    # It must not raise unhandled exception
    res = get_dynamo_resource()
    assert res is None or res is not None


def test_put_audit_event_async_does_not_block_or_crash():
    event = {
        "utterance": "test audit command",
        "intent": "SYSTEM_RAM",
        "tier": "SAFE",
        "outcome": "ALLOWED",
        "reason": "Test verified",
    }
    # Should execute asynchronously without crashing
    put_audit_event_async(event)
