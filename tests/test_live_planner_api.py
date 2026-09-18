import json
import os

import pytest

from actions.planner import default_tool_complete, schemas_from_registry
from actions.llm_client import key_manager


@pytest.mark.skipif(not key_manager.get_candidate_keys(), reason="no OpenRouter key")
def test_live_planner_native_tool_call():
    raw = default_tool_complete(
        [
            {"role": "system", "content": "Call fs_list_directory with location desktop. Do not answer in prose first."},
            {"role": "user", "content": "What files are on my desktop?"},
        ],
        schemas_from_registry(),
        timeout=20,
    )
    print("RAW_PLANNER_RESPONSE", json.dumps(raw, indent=2)[:4000])
    message = raw["choices"][0]["message"]
    calls = message.get("tool_calls") or []
    assert calls, raw
    assert "function" in calls[0]
    assert calls[0]["function"]["name"] in {s["function"]["name"] for s in schemas_from_registry()}
