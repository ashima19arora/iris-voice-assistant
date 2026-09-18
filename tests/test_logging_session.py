import logging

from actions.executor import execute_command
from actions.tools.registry import execute_tool


def test_structured_log_event_types(caplog, monkeypatch):
    caplog.set_level(logging.INFO, logger="iris")
    monkeypatch.setattr("actions.browser_actions.open_url", lambda *a, **k: True)
    monkeypatch.setattr("actions.executor.speak", lambda *a, **k: None)
    monkeypatch.setattr("actions.confirmation.speak", lambda *a, **k: None)
    monkeypatch.setattr("actions.feedback.speak", lambda *a, **k: None)
    execute_command("open youtube")
    execute_command(
        "what is photosynthesis",
        complete_fn=lambda messages, tools, **k: {"choices": [{"message": {"content": "A plant process.", "role": "assistant"}}]},
        gather_fn=lambda **k: {},
    )
    execute_tool("browser_navigate", {"url": "file:///C:/secret"})
    execute_tool("not_a_real_tool", {})
    from actions.confirmation import request_confirmation
    request_confirmation("Allow it?", listen_fn=lambda timeout=8: "nope")

    text = caplog.text
    assert "fast-path hit" in text
    assert "reasoning-path hit" in text
    assert "validation rejection" in text or "WARNING" in text
    assert "hallucinated tool" in text or "Unknown tool" in text
    assert "confirmation prompt" in text
    assert "confirmation response" in text
    print("SAMPLE_IRIS_LOG\n", text[-2000:])
