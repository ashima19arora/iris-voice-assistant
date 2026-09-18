import json
from pathlib import Path

from actions.config import FAST_PATH_MIN_CONFIDENCE
from actions.executor import TIER2_CUE, execute_command, route_utterance, should_use_reasoning_path
from actions.intent_parser import parse_intent

GOLDEN = json.loads(Path(__file__).with_name("golden_commands.json").read_text(encoding="utf-8"))

TIER1 = [
    "open youtube",
    "volume up",
    "scroll down",
    "open settings",
    "how much ram used",
]
TIER2 = [
    "what is photosynthesis",
    "open something weird unknown site xyz",
    "please rearrange my downloads by type",
    "summarize the article on this page and email it",
    "fill this form with my name and email",
]


def test_routing_table_ten_utterances(capsys):
    rows = []
    for phrase in TIER1:
        row = route_utterance(phrase)
        rows.append(row)
        assert row["tier"] == 1, row
    for phrase in TIER2:
        row = route_utterance(phrase)
        rows.append(row)
        assert row["tier"] == 2, row
    knowledge = route_utterance("what is photosynthesis")
    assert knowledge["intent"] == "KNOWLEDGE_QUERY"
    assert knowledge["tier"] == 2
    ambiguous = route_utterance("open something weird unknown site xyz")
    assert ambiguous["intent"] == "OPEN_WEBSITE"
    assert ambiguous["confidence"] < 0.6
    assert ambiguous["tier"] == 2
    for row in rows:
        print(f"ROUTE {row['tier']} intent={row['intent']} conf={row['confidence']:.3f} :: {row['utterance']}")
    assert len(rows) == 10


def test_golden_stays_tier1():
    for utterance, expected in [(g["utterance"], g["intent"]) for g in GOLDEN]:
        intent = parse_intent(utterance)
        assert intent.name == expected, (utterance, intent.name)
        assert should_use_reasoning_path(intent) is False
        assert intent.confidence >= FAST_PATH_MIN_CONFIDENCE


def test_cue_before_planner(monkeypatch):
    order = []
    monkeypatch.setattr("actions.executor.speak", lambda text, lang="en": order.append(("speak", text)))
    monkeypatch.setattr("actions.executor.gather_context", lambda **k: order.append(("context",)) or {})

    def complete(messages, tools, **kwargs):
        order.append(("llm",))
        return {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}

    execute_command("what is photosynthesis", complete_fn=complete, gather_fn=lambda **k: {})
    speaks = [item for item in order if item[0] == "speak"]
    assert speaks[0][1] == TIER2_CUE
    assert order.index(("speak", TIER2_CUE)) < order.index(("llm",))
