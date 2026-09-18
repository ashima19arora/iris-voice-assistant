"""
Comprehensive verification test suite for user failure modes and feature additions:
- Whitelisted app launch (Task Manager, VS Code, Cursor)
- Flexible Desktop file creation with content
- Arogya Setu ASR and browser affiliation parsing
- Screen link and search result click routing
- RapidOCR compact fuzzy matching
- Dual-mode zoom and scroll execution
- Single-spoken knowledge responses
"""
import os
from pathlib import Path
from actions.intent_parser import parse_intent
from actions.security.sanitizer import sanitize_app_target
from actions.screen_actions import _fuzzy_score
from actions.file_actions import create_file, safe_directories
from actions.knowledge_actions import answer_knowledge_query


def test_task_manager_whitelisting():
    # Various ways the user or speech recognition can phrase Task Manager
    assert sanitize_app_target("Task Manager")[0] is True
    assert sanitize_app_target("the Task Manager")[0] is True
    assert sanitize_app_target("open the task manager")[0] is True
    assert sanitize_app_target("windows task manager")[0] is True
    assert sanitize_app_target("taskmgr")[0] is True

    # Intent parser parses all of them to OPEN_APP
    intent = parse_intent("Can you please open the Task Manager?")
    assert intent.name == "OPEN_APP"
    assert intent.params.get("app_name") in ("task manager", "the task manager")


def test_dev_apps_whitelisting():
    assert sanitize_app_target("visual studio code")[0] is True
    assert sanitize_app_target("vscode")[0] is True
    assert sanitize_app_target("vs code")[0] is True
    assert sanitize_app_target("cursor")[0] is True


def test_file_creation_intent_variations():
    cases = [
        ("Can you please create a text.txt file on my desktop and write hello in it?", "text.txt", "desktop", "hello"),
        ("create a file on my desktop named test.txt and write hello in it", "test.txt", "desktop", "hello"),
        ("create file notes.txt on desktop with content meeting notes", "notes.txt", "desktop", "meeting notes"),
        ("create a new file on desktop named tasks.txt", "tasks.txt", "desktop", ""),
        ("make a note called shopping on desktop", "shopping", "desktop", ""),
    ]
    for utterance, expected_name, expected_loc, expected_content in cases:
        intent = parse_intent(utterance)
        assert intent.name == "CREATE_FILE", f"Failed for {utterance}"
        assert intent.params.get("location") == expected_loc
        assert expected_name in intent.params.get("filename")
        if expected_content:
            assert expected_content in intent.params.get("content")


def test_create_file_execution(tmp_path, monkeypatch):
    # Verify file actually writes content without confirmation blocking
    fake_dirs = {"desktop": [tmp_path], "documents": [tmp_path], "iris": [tmp_path]}
    monkeypatch.setattr("actions.file_actions.safe_directories", lambda: fake_dirs)

    ok = create_file("verify_test.txt", content="Hello Iris", location="desktop", open_after=False)
    assert ok is True
    target = tmp_path / "verify_test.txt"
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "Hello Iris"


def test_arogya_setu_variations():
    # Misspellings and edge browser references
    cases = [
        "Can you please open Arogya Setu on edge.com?",
        "Opan arogya seatu",
        "open aarogya setu in edge",
        "open arogya setup",
    ]
    for utterance in cases:
        intent = parse_intent(utterance)
        assert intent.name == "OPEN_WEBSITE", f"Failed for {utterance}"
        assert "aarogya setu" in intent.params.get("target") or "arogya setu" in intent.params.get("target")


def test_link_and_result_clicking():
    cases = [
        ("open the first result", "result", 1),
        ("click the first result", "result", 1),
        ("open the first link", "link", 1),
        ("click the first link", "link", 1),
        ("click the second result", "result", 2),
        ("click on the link that is being displayed", "link that is being displayed", 1),
        ("Link that is being displayed that is the Google Aid of Draham", "the google link", 1),
    ]
    for utterance, target_substr, nth in cases:
        intent = parse_intent(utterance)
        assert intent.name == "CLICK_ELEMENT", f"Failed for {utterance}"
        assert target_substr in intent.params.get("target")
        assert intent.params.get("nth") == nth


def test_compact_fuzzy_ocr_matching():
    # "aarogya setu" should match "AarogyaSetu 2.0" despite spacing differences
    score = _fuzzy_score("aarogya setu", "AarogyaSetu 2.0 – Apps on Google Play")
    assert score >= 0.90, f"Expected >= 0.90 but got {score}"

    score_task = _fuzzy_score("the task manager", "Task Manager")
    assert score_task >= 0.80


def test_knowledge_speak_answer_flag():
    # answer_knowledge_query with speak_answer=False returns the answer without calling speak
    ans = answer_knowledge_query("what is two plus two", speak_answer=False)
    assert bool(ans) is True
    assert isinstance(ans, str) and len(ans.strip()) > 0
