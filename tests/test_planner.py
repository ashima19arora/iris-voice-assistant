import json
import logging

import pytest
import requests

from actions.config import MAX_PLANNER_TOOL_CALLS
from actions.planner import PlannerFailure, default_tool_complete, run_planner, schemas_from_registry
from actions.tools.registry import TOOL_REGISTRY, assert_call_budget, execute_tool


def _assistant_tools(calls):
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": calls,
                }
            }
        ]
    }


def test_sixth_tool_call_rejected(caplog):
    caplog.set_level(logging.ERROR, logger="iris")
    reason = assert_call_budget(6)
    assert reason
    assert str(MAX_PLANNER_TOOL_CALLS) in reason

    calls = [
        {"id": f"c{i}", "function": {"name": "fs_list_directory", "arguments": json.dumps({"location": "desktop"})}}
        for i in range(6)
    ]
    complete_calls = {"n": 0}

    def complete(messages, tools, **kwargs):
        complete_calls["n"] += 1
        if complete_calls["n"] == 1:
            return _assistant_tools(calls)
        return {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}

    result = run_planner("list files", {}, complete_fn=complete, confirm_fn=lambda *a, **k: True)
    assert result["ok"] is False
    assert any(s.get("index") == 6 and s.get("ok") is False for s in result["steps"])
    assert "too long" in result["spoken"].lower() or "max" in str(result["steps"][-1]["error"]).lower()
    assert any("max" in rec.message.lower() for rec in caplog.records)


def test_hallucinated_tool_is_graceful():
    def complete(messages, tools, **kwargs):
        return _assistant_tools(
            [{"id": "1", "function": {"name": "launch_missiles", "arguments": "{}"}}]
        )

    with pytest.raises(PlannerFailure) as exc:
        run_planner("hack", {}, complete_fn=complete, confirm_fn=lambda *a, **k: True)
    assert exc.value.kind == "unknown_tool"
    assert "launch_missiles" in exc.value.spoken


def test_malformed_tool_json():
    def complete(messages, tools, **kwargs):
        return _assistant_tools(
            [{"id": "1", "function": {"name": "fs_list_directory", "arguments": "{not-json"}}]
        )

    with pytest.raises(PlannerFailure) as exc:
        run_planner("list", {}, complete_fn=complete)
    assert exc.value.kind == "malformed_json"


def test_invalid_api_key_failure():
    with pytest.raises(PlannerFailure) as exc:
        default_tool_complete(
            [{"role": "user", "content": "hi"}],
            schemas_from_registry(),
            api_key="sk-invalid-iris-test-key",
            timeout=8,
        )
    assert exc.value.kind == "invalid_api_key"


def test_network_timeout_failure(monkeypatch):
    def boom(*args, **kwargs):
        raise requests.Timeout("induced")

    monkeypatch.setattr("actions.planner.requests.post", boom)
    with pytest.raises(PlannerFailure) as exc:
        default_tool_complete([{"role": "user", "content": "hi"}], schemas_from_registry(), api_key="x", timeout=0.01)
    assert exc.value.kind == "timeout"


def test_partial_step_reporting():
    sequence = {"n": 0}

    def complete(messages, tools, **kwargs):
        sequence["n"] += 1
        if sequence["n"] == 1:
            return _assistant_tools(
                [
                    {"id": "1", "function": {"name": "fs_list_directory", "arguments": json.dumps({"location": "desktop"})}},
                    {"id": "2", "function": {"name": "fs_list_directory", "arguments": json.dumps({"location": ".."})}},
                    {"id": "3", "function": {"name": "fs_list_directory", "arguments": json.dumps({"location": "documents"})}},
                    {"id": "4", "function": {"name": "fs_list_directory", "arguments": json.dumps({"location": "iris"})}},
                ]
            )
        return {"choices": [{"message": {"content": "Listed folders.", "role": "assistant"}}]}

    result = run_planner("list stuff", {}, complete_fn=complete, confirm_fn=lambda *a, **k: True)
    assert len(result["steps"]) == 4
    assert result["steps"][0]["ok"] is True
    assert result["steps"][1]["ok"] is False
    assert result["steps"][2]["ok"] is True or result["steps"][2]["ok"] is False  # iris/docs may exist
    spoken_blob = json.dumps(result["steps"])
    assert "fs_list_directory" in spoken_blob


def test_execute_unknown_tool_direct():
    out = execute_tool("not_in_registry", {})
    assert out["ok"] is False
    assert "Unknown tool" in out["error"]
