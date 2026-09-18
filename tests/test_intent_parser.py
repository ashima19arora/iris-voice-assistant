"""Tier-1 intent parser tests: variants, negatives, golden regression, overlap, latency."""
import json
import time
from pathlib import Path

import pytest

from actions.intent_parser import RULES, clean_speech_text, parse_intent, parse_ordinal
from actions.registry import INTENT_HANDLERS

GOLDEN_PATH = Path(__file__).with_name("golden_commands.json")
GOLDEN = [(row["utterance"], row["intent"]) for row in json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))]


INTENT_VARIANTS = {
    "EXIT_ASSISTANT": ["goodbye", "bye", "exit", "stop listening", "iris band karo"],
    "LOCK_SCREEN": [
        "lock the computer",
        "lock screen",
        "computer lock karo",
        "lock the pc",
        "screen lock kardo",
    ],
    "SCREENSHOT": [
        "take a screenshot",
        "capture the screen",
        "screenshot lo",
        "take screenshot",
        "screenshot kheencho",
    ],
    "VOLUME_UP": ["volume up", "aawaz badhao", "turn up the volume", "louder", "volume badhao"],
    "VOLUME_DOWN": [
        "volume down",
        "aawaz kam karo",
        "turn down volume",
        "softer",
        "volume kam kardo",
    ],
    "VOLUME_MUTE": ["mute", "unmute", "aawaz band karo", "silence audio", "mute karo"],
    "SYSTEM_RAM": [
        "check ram",
        "ram kitna used hai",
        "uh how much ram used",
        "how much memory is occupied",
        "RAM usage",
    ],
    "SYSTEM_BATTERY": [
        "battery percentage",
        "how much battery is left",
        "battery kitni bachi",
        "battery status",
        "power remaining",
    ],
    "SYSTEM_CPU": [
        "cpu usage",
        "processor load",
        "cpu kitna",
        "cpu utilization",
        "processor status",
    ],
    "SYSTEM_TIME": [
        "what is the time",
        "what time is it",
        "current time",
        "time kya",
        "samay kya",
    ],
    "SYSTEM_DATE": [
        "what is the date",
        "what day is it",
        "today's date",
        "date kya",
        "taareekh kya",
    ],
    "BROWSER_SCROLL_TOP": [
        "scroll to top",
        "go to top",
        "top of page",
        "sabse upar jao",
        "scroll to top please",
    ],
    "BROWSER_SCROLL_BOTTOM": [
        "scroll to bottom",
        "go to bottom",
        "bottom of page",
        "sabse neeche jao",
        "scroll to bottom please",
    ],
    "BROWSER_SCROLL_DOWN": [
        "scroll down",
        "neeche scroll karo",
        "iris scroll kar do neeche",
        "scrawl down",
        "page down",
    ],
    "BROWSER_SCROLL_UP": [
        "scroll up",
        "upar scroll karo",
        "scroll karo upar",
        "page up",
        "upar jao",
    ],
    "BROWSER_ZOOM_IN": ["zoom in", "zoom in browser", "zoom badao", "bada dikhao", "zoom in please"],
    "BROWSER_ZOOM_OUT": [
        "zoom out",
        "zoom out browser",
        "zoom kam karo",
        "chhota dikhao",
        "zoom out please",
    ],
    "BROWSER_ZOOM_RESET": [
        "reset zoom",
        "normal zoom",
        "default zoom",
        "zoom reset karo",
        "reset zoom please",
    ],
    "SEARCH_WEB": [
        "search for cats",
        "google python tutorials",
        "look up weather",
        "cats search karo",
        "dhoondo karo delhi weather",
    ],
    "OPEN_APP": [
        "open settings",
        "settings kholo",
        "open, uh, settings please",
        "open notepad",
        "seddings kholo",
        "open the task manager",
    ],
    "OPEN_WEBSITE": [
        "open youtube",
        "youtube kholo please",
        "open open youtube",
        "open, uh, youtube please",
        "visit india.gov.in",
    ],
    "CREATE_FILE": [
        "create a text file on the desktop",
        "make a note called Tasks on desktop",
        "desktop par file banao",
        "create note shopping list",
        "write a txt file named ideas",
        "create a text.txt file on my desktop and write hello in it",
    ],
    "BROWSER_NEW_TAB": ["new tab", "open a new tab", "create tab", "naya tab", "open new tab"],
    "BROWSER_CLOSE_TAB": ["close tab", "tab band karo", "close this tab", "shut tab", "exit tab"],
    "BROWSER_REOPEN_TAB": [
        "reopen tab",
        "restore tab",
        "undo close tab",
        "reopen tab please",
        "restore tab please",
    ],
    "BROWSER_SWITCH_TAB": [
        "next tab",
        "switch tab",
        "agla tab",
        "previous tab",
        "pichla tab",
    ],
    "BROWSER_REFRESH": ["refresh", "reload", "refresh page", "reload page", "refresh please"],
    "BROWSER_OPEN_HISTORY": [
        "open history",
        "browser history",
        "show history",
        "history dikhao",
        "history kholo",
    ],
    "BROWSER_OPEN_DOWNLOADS": [
        "open downloads",
        "browser downloads",
        "show downloads",
        "downloads dikhao",
        "downloads kholo",
    ],
    "BROWSER_BOOKMARK": [
        "bookmark this page",
        "bookmark page",
        "page bookmark karo",
        "bookmark",
        "bookmark this",
    ],
    "BROWSER_GO_BACK": ["go back", "back page", "previous page", "peeche jao", "go back please"],
    "BROWSER_GO_FORWARD": [
        "go forward",
        "forward page",
        "next page history",
        "aage jao",
        "go forward please",
    ],
    "BROWSER_FULLSCREEN": [
        "toggle fullscreen",
        "fullscreen mode",
        "full screen browser",
        "toggle fullscreen please",
        "fullscreen mode please",
    ],
    "BROWSER_FIND_ON_PAGE": [
        "find on page login",
        "search on page password",
        "find in page submit",
        "search page for email",
        "page par dhoondo login",
    ],
    "WINDOW_SNAP_LEFT": [
        "snap window left",
        "snap left",
        "left snap",
        "left snap karo",
        "snap left please",
    ],
    "WINDOW_SNAP_RIGHT": [
        "snap window right",
        "snap right",
        "right snap",
        "right snap karo",
        "snap right please",
    ],
    "WINDOW_TASK_VIEW": [
        "task view",
        "open task view",
        "show tasks",
        "task view dikhao",
        "open task view please",
    ],
    "DESKTOP_SWITCH": [
        "next desktop",
        "switch to next desktop",
        "agla desktop",
        "previous desktop",
        "pichla desktop",
    ],
    "DESKTOP_NEW": [
        "new desktop",
        "create desktop",
        "naya desktop",
        "new desktop please",
        "create desktop please",
    ],
    "DESKTOP_CLOSE": [
        "close desktop",
        "delete desktop",
        "desktop band karo",
        "close desktop please",
        "delete desktop please",
    ],
    "WINDOW_CLOSE": [
        "close window",
        "window band karo",
        "close this window",
        "shut window",
        "exit window",
    ],
    "WINDOW_MINIMIZE": [
        "minimize window",
        "minimize",
        "hide window",
        "minimize window please",
        "minimize please",
    ],
    "WINDOW_MAXIMIZE": [
        "maximize window",
        "maximize",
        "maximize window please",
        "maximize please",
        "maximize window now",
    ],
    "SHOW_DESKTOP": [
        "show desktop",
        "go to desktop",
        "minimize all",
        "desktop dikhao",
        "show desktop please",
    ],
    "WINDOW_SWITCH": [
        "switch window",
        "switch app",
        "alt tab",
        "next window",
        "switch window please",
    ],
    "FORM_NEXT_FIELD": ["press tab", "next field", "tab key", "agla field", "tab dabao"],
    "FORM_PREV_FIELD": [
        "previous field",
        "prev field",
        "shift tab",
        "back field",
        "pichla field",
    ],
    "FORM_SUBMIT": ["submit form", "press enter", "hit enter", "enter dabao", "form submit karo"],
    "FORM_TOGGLE_CHECKBOX": [
        "toggle checkbox",
        "check box",
        "press space",
        "space dabao",
        "select checkbox",
    ],
    "FORM_FILL_FIELD": [
        "fill field with hello",
        "fill in input world",
        "fill box with test",
        "fill field hello",
        "fill input with name",
    ],
    "SELECT_ALL": [
        "select all",
        "select all text",
        "highlight all",
        "sab select karo",
        "select all please",
    ],
    "CLEAR_FIELD": [
        "clear the field",
        "clear input",
        "erase the text",
        "field khali karo",
        "clear the box",
    ],
    "COPY_TEXT": ["copy", "copy this", "copy text", "copy karo", "copy that"],
    "PASTE_TEXT": ["paste", "paste this", "paste text", "paste karo", "paste here"],
    "UNDO_ACTION": ["undo", "undo that", "undo last action", "undo karo", "undo edit"],
    "COMPOUND_OPEN_AND_TYPE": [
        "open whatsapp and type hello",
        "open notepad and then write notes",
        "open chrome and send hi",
        "open whatsapp and message dinner",
        "open slack and type standup",
    ],
    "TYPE_AND_SEND": [
        "type hello and send",
        "write meeting notes and send it",
        "type and send on my way",
        "send message lunch aur bhej do",
        "write hello aur bhej do",
    ],
    "SEND_MESSAGE": [
        "send message",
        "send it",
        "message bhej do",
        "send karo",
        "send message please",
    ],
    "TYPE_TEXT": [
        "type hello world",
        "write my name",
        "enter text password",
        "type karo hello",
        "likho karo namaste",
    ],
    "MEDIA_PLAY_PAUSE": [
        "play music",
        "pause music",
        "resume playback",
        "gana bajao",
        "gana roko",
    ],
    "READ_SCREEN": [
        "read the screen",
        "what is on the screen",
        "screen padho",
        "screen dikhao",
        "read screen",
    ],
    "DOUBLE_CLICK_ELEMENT": [
        "double click the file",
        "double tap icon",
        "double click folder",
        "file par do baar click karo",
        "double click result",
    ],
    "RIGHT_CLICK_ELEMENT": [
        "right click the file",
        "right tap icon",
        "right click folder",
        "file par right click karo",
        "right click menu",
    ],
    "HOVER_ELEMENT": [
        "hover over menu",
        "hover on button",
        "move mouse to search",
        "menu par hover karo",
        "move cursor over link",
    ],
    "CLICK_ELEMENT": [
        "click the first result",
        "click result number 2",
        "home par click karo",
        "click submit",
        "tap the third link",
    ],
    "GREETING": ["hello", "hi", "namaste", "who are you", "what can you do"],
    "KNOWLEDGE_QUERY": [
        "what is photosynthesis",
        "who is the prime minister",
        "tell me about mars",
        "photosynthesis kya hai",
        "explain gravity",
    ],
}


NEGATIVES = [
    ("I watch youtube videos sometimes", "OPEN_WEBSITE"),
    ("tab band karo", "EXIT_ASSISTANT"),
    ("tab band karo", "WINDOW_CLOSE"),
    ("close the window", "BROWSER_CLOSE_TAB"),
    ("double click file", "CLICK_ELEMENT"),
    ("scroll to top", "BROWSER_SCROLL_UP"),
    ("search on page login", "SEARCH_WEB"),
    ("close tab", "WINDOW_CLOSE"),
    ("close window", "EXIT_ASSISTANT"),
    ("maximize", "BROWSER_FULLSCREEN"),
    ("play music", "TYPE_TEXT"),
    ("open settings", "OPEN_WEBSITE"),
]


OVERLAP = [
    ("close tab", "BROWSER_CLOSE_TAB"),
    ("close window", "WINDOW_CLOSE"),
    ("exit tab", "BROWSER_CLOSE_TAB"),
    ("exit window", "WINDOW_CLOSE"),
    ("exit", "EXIT_ASSISTANT"),
    ("double click file", "DOUBLE_CLICK_ELEMENT"),
    ("right click file", "RIGHT_CLICK_ELEMENT"),
    ("click file", "CLICK_ELEMENT"),
    ("scroll to top", "BROWSER_SCROLL_TOP"),
    ("scroll up", "BROWSER_SCROLL_UP"),
    ("search on page login", "BROWSER_FIND_ON_PAGE"),
    ("search for login", "SEARCH_WEB"),
    ("open history", "BROWSER_OPEN_HISTORY"),
    ("open downloads", "BROWSER_OPEN_DOWNLOADS"),
    ("open youtube", "OPEN_WEBSITE"),
    ("open settings", "OPEN_APP"),
    ("open notepad", "OPEN_APP"),
    ("desktop band karo", "DESKTOP_CLOSE"),
    ("window band karo", "WINDOW_CLOSE"),
    ("iris band karo", "EXIT_ASSISTANT"),
]


def test_golden_regression():
    for phrase, expected in GOLDEN:
        intent = parse_intent(phrase)
        assert intent.name == expected, (phrase, intent.name)


def test_gov_in_target():
    assert "gov" in parse_intent("open gov.in").params["target"]


def test_settings_app_param():
    assert parse_intent("open setting for me please").params["app_name"] == "settings"


def test_create_file_with_content_not_type_text():
    intent = parse_intent("create a text.txt file on my desktop and write hello in it")
    assert intent.name == "CREATE_FILE", intent.name
    assert "text" in intent.params["filename"].lower()
    assert intent.params["location"] == "desktop"
    assert "hello" in (intent.params.get("content") or "").lower()


def test_open_task_manager_is_app():
    intent = parse_intent("Can you please open the Task Manager?")
    assert intent.name == "OPEN_APP"
    assert "task" in intent.params["app_name"]


def test_open_aarogya_setu_is_website():
    intent = parse_intent("Opan arogya seatu")
    assert intent.name == "OPEN_WEBSITE"
    assert "aarogya" in intent.params["target"]


def test_click_ordinals_consistent():
    a = parse_intent("click the second result")
    b = parse_intent("click result 2")
    c = parse_intent("click result number two")
    assert a.name == b.name == c.name == "CLICK_ELEMENT"
    assert a.params["nth"] == b.params["nth"] == c.params["nth"] == 2


def test_asr_filler_and_repeat():
    assert parse_intent("open, uh, youtube please").name in ("OPEN_WEBSITE", "OPEN_APP")
    assert parse_intent("open open youtube").name == "OPEN_WEBSITE"
    assert "youtube" in clean_speech_text("open, uh, youtube please")


def test_homophone_scroll():
    assert parse_intent("scrawl down").name == "BROWSER_SCROLL_DOWN"


def test_code_switching():
    assert parse_intent("youtube kholo please").name == "OPEN_WEBSITE"
    assert parse_intent("iris scroll kar do neeche").name == "BROWSER_SCROLL_DOWN"
    assert parse_intent("settings kholo").name == "OPEN_APP"


def test_close_tab_vs_window():
    assert parse_intent("close tab").name == "BROWSER_CLOSE_TAB"
    assert parse_intent("close window").name == "WINDOW_CLOSE"


def test_double_click_outranks_click():
    intent = parse_intent("double click the file")
    assert intent.name == "DOUBLE_CLICK_ELEMENT"


def test_fallback_confidence_below_tier2_threshold():
    intent = parse_intent("open something weird unknown site xyz")
    assert intent.name == "OPEN_WEBSITE"
    assert intent.confidence < 0.6


def test_exact_open_youtube_high_confidence():
    intent = parse_intent("open youtube")
    assert intent.name == "OPEN_WEBSITE"
    assert intent.confidence >= 0.8


def test_param_length_cap():
    huge = "create a file named " + ("x" * 5000)
    intent = parse_intent(huge)
    if intent.name == "CREATE_FILE":
        assert len(intent.params["filename"]) <= 200


def test_path_traversal_stripped():
    intent = parse_intent("create a file named ../etc/passwd")
    assert intent.name == "CREATE_FILE"
    assert ".." not in intent.params["filename"]
    assert "`" not in intent.params["filename"]


def test_empty_create_gets_default_name():
    intent = parse_intent("create a txt file on desktop")
    assert intent.params.get("filename")


def test_no_intents_dropped_vs_registry():
    parser_names = {rule.name for rule in RULES}
    handler_names = set(INTENT_HANDLERS) - {"UNKNOWN"}
    missing = handler_names - parser_names
    assert not missing, f"registry intents missing from parser: {missing}"


@pytest.mark.parametrize("intent_name,phrases", list(INTENT_VARIANTS.items()))
def test_five_variants_per_intent(intent_name, phrases):
    assert len(phrases) >= 5
    for phrase in phrases:
        got = parse_intent(phrase).name
        assert got == intent_name, f"{phrase!r} -> {got} expected {intent_name}"


@pytest.mark.parametrize("phrase,not_intent", NEGATIVES)
def test_negatives(phrase, not_intent):
    assert parse_intent(phrase).name != not_intent, phrase


@pytest.mark.parametrize("phrase,expected", OVERLAP)
def test_overlap_disambiguation(phrase, expected):
    assert parse_intent(phrase).name == expected, phrase


def test_parse_ordinal_helper():
    assert parse_ordinal("second result")[1] == 2
    assert parse_ordinal("result number two")[1] == 2
    assert parse_ordinal("result 3")[1] == 3


def test_rules_are_compiled_and_prioritized():
    assert RULES
    priorities = [r.priority for r in RULES]
    assert priorities == sorted(priorities, reverse=True)
    for rule in RULES:
        assert rule.patterns
        for pattern in rule.patterns:
            assert pattern.search  # compiled Pattern


def test_redos_worst_case_stays_fast():
    junk = ("open " + "a" * 4000 + " " + "b" * 4000)
    start = time.perf_counter()
    parse_intent(junk)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 200, elapsed_ms


def test_latency_batch():
    corpus = [p for p, _ in GOLDEN]
    for phrases in INTENT_VARIANTS.values():
        corpus.extend(phrases)
    corpus.extend([n[0] for n in NEGATIVES])
    corpus.extend([o[0] for o in OVERLAP])
    while len(corpus) < 220:
        corpus.append(corpus[len(corpus) % max(len(GOLDEN), 1)] + " please")
    times = []
    parse_intent("open youtube")
    for phrase in corpus:
        start = time.perf_counter()
        parse_intent(phrase)
        times.append((time.perf_counter() - start) * 1000)
    times.sort()
    p50 = times[len(times) // 2]
    p95 = times[int(len(times) * 0.95)]
    assert p50 < 50
    assert p95 < 50
    print(f"\nparse_intent n={len(times)} p50={p50:.3f}ms p95={p95:.3f}ms max={times[-1]:.3f}ms")
