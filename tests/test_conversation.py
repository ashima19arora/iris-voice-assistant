"""Tests for multi-turn conversation memory and context resolution."""
import time
from actions.conversation import (
    ConversationManager,
    ConversationTurn,
    record_user_turn,
    record_assistant_turn,
    get_history,
    clear_history,
)
from actions.executor import execute_command


def test_conversation_turn_creation():
    turn = ConversationTurn(role="user", content="Hello Iris", lang="en")
    assert turn.role == "user"
    assert turn.content == "Hello Iris"
    assert turn.lang == "en"
    d = turn.to_dict()
    assert d["role"] == "user"
    assert d["content"] == "Hello Iris"


def test_conversation_manager_rolling_history():
    cm = ConversationManager(max_turns=4, ttl_seconds=60)
    cm.record_user_turn("What is the capital of France?")
    cm.record_assistant_turn("Paris is the capital of France.")
    cm.record_user_turn("What is its population?")
    cm.record_assistant_turn("Paris has around 2.1 million residents.")

    hist = cm.get_history(max_turns=4)
    assert len(hist) == 4
    assert hist[0]["content"] == "What is the capital of France?"
    assert hist[1]["content"] == "Paris is the capital of France."
    assert hist[2]["content"] == "What is its population?"
    assert hist[3]["content"] == "Paris has around 2.1 million residents."

    # Test rolling overflow
    cm.record_user_turn("Is it raining there?")
    hist5 = cm.get_history(max_turns=4)
    assert len(hist5) == 4
    # The oldest turn should have rolled off
    assert hist5[0]["content"] == "Paris is the capital of France."
    assert hist5[-1]["content"] == "Is it raining there?"


def test_conversation_ttl_expiration(monkeypatch):
    cm = ConversationManager(max_turns=5, ttl_seconds=1.0)
    cm.record_user_turn("Old query")
    cm.record_assistant_turn("Old answer")

    # Time advance by 2.5 seconds
    orig_time = time.time()
    monkeypatch.setattr(time, "time", lambda: orig_time + 2.5)

    hist = cm.get_history()
    assert len(hist) == 0


def test_conversation_reset_command():
    clear_history()
    record_user_turn("Question 1")
    record_assistant_turn("Answer 1")
    assert len(get_history()) == 2

    # Execute reset command
    result = execute_command("clear context")
    assert result.success is True
    assert result.intent == "RESET_CONVERSATION"
    assert len(get_history()) == 0


def test_hindi_conversation_reset():
    clear_history()
    record_user_turn("भारत की राजधानी?")
    record_assistant_turn("नई दिल्ली")
    assert len(get_history()) == 2

    result = execute_command("नयी बातचीत", lang="hi")
    assert result.success is True
    assert result.intent == "RESET_CONVERSATION"
    assert "रीसेट" in result.message
    assert len(get_history()) == 0
