import ast
from pathlib import Path

from actions.config import FAST_PATH_MIN_CONFIDENCE, TIER2_ALWAYS_INTENTS


def test_fast_path_threshold_is_documented_default():
    assert FAST_PATH_MIN_CONFIDENCE == 0.6
    assert "KNOWLEDGE_QUERY" in TIER2_ALWAYS_INTENTS


def test_no_hardcoded_threshold_outside_config():
    root = Path(__file__).resolve().parents[1]
    skip = {
        root / "actions" / "config.py",
        root / "actions" / "intent_parser.py",  # frozen; docstring only
        root / "tests" / "test_intent_parser.py",
    }
    offenders = []
    for path in root.rglob("*.py"):
        if path in skip or ".venv" in path.parts or "__pycache__" in path.parts:
            continue
        if "tests" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        if "0.6" not in source:
            continue
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and node.value == 0.6:
                offenders.append(f"{path}:{node.lineno}")
    assert offenders == []
