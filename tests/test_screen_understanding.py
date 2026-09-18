"""
Tests for Screen Scene Understanding, Native UIA, Mouse Pointer Clicking,
and Layout-Aware OCR in Iris.
"""
from pathlib import Path
from PIL import Image
import pytest

from actions.intent_parser import parse_intent
from actions.screen_actions import (
    find_element_by_text,
    _fuzzy_score,
    ocr_screen,
    click_at_mouse_position,
)
from actions.screen_understanding import (
    get_active_window_info,
    get_background_apps,
    analyze_screen_content,
)
from actions.registry import INTENT_HANDLERS


def test_click_at_mouse_intents():
    """Verify variations of mouse pointer clicking parse directly to CLICK_AT_MOUSE."""
    phrases = [
        "Click where the mouse is pointing currently please",
        "click where the mouse is pointing",
        "click where mouse is",
        "click here",
        "click at cursor",
        "click current position",
    ]
    for p in phrases:
        intent = parse_intent(p)
        assert intent.name == "CLICK_AT_MOUSE", f"Failed for '{p}', got {intent.name}"
        assert intent.params.get("double") is False
        assert intent.params.get("right") is False

    # Double click at mouse
    intent = parse_intent("double click where the mouse is pointing")
    assert intent.name == "CLICK_AT_MOUSE"
    assert intent.params.get("double") is True

    # Right click at mouse
    intent = parse_intent("right click where the mouse is pointing")
    assert intent.name == "CLICK_AT_MOUSE"
    assert intent.params.get("right") is True


def test_describe_screen_and_what_is_open_intents():
    """Verify screen scene and background process query intents."""
    screen_queries = [
        "what is on my screen",
        "what is on the screen",
        "what am i looking at",
        "read my screen",
        "read the screen",
        "summarize my screen",
    ]
    for q in screen_queries:
        intent = parse_intent(q)
        assert intent.name == "READ_SCREEN", f"Failed for '{q}', got {intent.name}"

    app_queries = [
        "what is open",
        "what is open right now",
        "what is running in the background",
        "what is happening in the background",
        "what apps are open",
        "what applications are open",
    ]
    for q in app_queries:
        intent = parse_intent(q)
        assert intent.name == "WHAT_IS_OPEN", f"Failed for '{q}', got {intent.name}"


def test_multi_sentence_antecedent_resolution():
    """Verify multi-sentence conversational utterances resolve pronoun to informative clause."""
    raw = "Click on the first link that is open that is Bajrangi Bhaijam Songs. Click on that please"
    intent = parse_intent(raw)
    assert intent.name == "CLICK_ELEMENT"
    assert "bajrangi bhaijam songs" in intent.params["target"].lower()
    assert intent.params["nth"] == 1


def test_relative_clause_target_extraction():
    """Verify relative clauses are cleanly stripped to extract the actual target."""
    utterance = "Can you please click on the first link on the screen of YouTube Badrangi Bhaijan Songs?"
    intent = parse_intent(utterance)
    assert intent.name == "CLICK_ELEMENT"
    assert "badrangi bhaijan songs" in intent.params["target"].lower()


def test_pronoun_safety_guard_rejects_chat_copilot():
    """Ensure bare pronoun 'that' returns None and does not falsely match 'Chat'."""
    fake_ocr = [
        {"text": "Chat", "bbox": [[1000, 40], [1050, 40], [1050, 60], [1000, 60]], "confidence": 0.9},
        {"text": "Search", "bbox": [[200, 100], [260, 100], [260, 120], [200, 120]], "confidence": 0.9},
    ]
    assert find_element_by_text("that", fake_ocr) is None
    assert find_element_by_text("this", fake_ocr) is None
    assert find_element_by_text("it", fake_ocr) is None


def test_layout_aware_search_result_selection():
    """
    On a real search page layout, generic 'first link' must select the result area
    rather than the top search input box (y < 230) or tabs.
    """
    screenshot_path = Path(r"C:\Users\Mayank Garg\.gemini\antigravity-ide\brain\2150918d-4205-4426-a29f-9702670f6380\.user_uploaded\media_1789705907402.png")
    if not screenshot_path.exists():
        pytest.skip("Test screenshot artifact not available in environment")

    img = Image.open(screenshot_path)
    ocr_results = ocr_screen(img)
    assert len(ocr_results) > 10

    # 'first link' must select a search result below header (y >= 230)
    match = find_element_by_text("first link", ocr_results)
    assert match is not None
    # Must NOT be the search query box at (228, 107) or tabs at y=156
    assert match["center"][1] >= 230
    assert match["center"][0] < 1400  # not sidebar
    assert match["text"] in ("Google Play", "AarogyaSetu2.0-AppsonGooglePlay", "https://play.google.com > store > apps > details > id=nic...")


def test_background_apps_and_window_info():
    """Verify get_background_apps and get_active_window_info return structured data."""
    win = get_active_window_info()
    assert isinstance(win, dict)
    assert "title" in win
    assert "app_name" in win

    apps = get_background_apps()
    assert isinstance(apps, list)
    for app in apps:
        assert "name" in app
        assert "process" in app


def test_action_dispatch_registration():
    """Verify new intents are properly registered in INTENT_HANDLERS."""
    assert "CLICK_AT_MOUSE" in INTENT_HANDLERS
    assert "READ_SCREEN" in INTENT_HANDLERS
    assert "WHAT_IS_OPEN" in INTENT_HANDLERS
