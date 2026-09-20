"""
Iris Intent Parser — data-driven Tier-1 fast path.

Patterns are compiled once at import. Rules are a list of
{name, priority, patterns, extractor}. Higher priority wins;
equal priority keeps list order. Do not add elif chains for new commands —
append a Rule.

Priority bands (explicit):
  100 exit/lock          90 volume/screenshot     88 system metrics
  86 scroll/zoom         84 search                82 open settings/apps/sites
  80 create file         78 tabs                  76 windows
  70 forms/clipboard     60 type/send             50 clicks (double/right before single)
  40 greeting            20 low-confidence fallbacks
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Pattern, Tuple

# Shared Hindi verb forms — reuse everywhere, do not fork per intent.
HI_VERB = r"(?:karo|kardo|kar\s+do|karna(?:\s+hai)?|kariye|kijiye)"
HI_OPEN = r"(?:kholo|khol|chalao|chala|open)"
OPEN_VERB = rf"(?:open|launch|start|go\s+to|navigate\s+to|visit|{HI_OPEN})"

KNOWN_SITES = (
    r"youtube|whatsapp(?:\s+web)?|github|gmail|reddit|wikipedia|"
    r"twitter|x|netflix|amazon|maps|chatgpt|linkedin|google|"
    r"aarogya\s+setu"
)
KNOWN_APPS = (
    r"notepad|calculator|calc|terminal|command\s+prompt|cmd|"
    r"explorer|files|file\s+explorer|paint|settings|whatsapp|"
    r"task\s+manager|taskmgr|chrome|edge|firefox"
)

MAX_PARAM_LEN = 200
UNSAFE_PARAM = re.compile(r"[\x00;`|$<>]|(\.\.[\\/]?)")

ORDINAL_WORDS = {
    "first": 1, "1st": 1, "one": 1, "1": 1,
    "second": 2, "2nd": 2, "two": 2, "2": 2,
    "third": 3, "3rd": 3, "three": 3, "3": 3,
    "fourth": 4, "4th": 4, "four": 4, "4": 4,
    "fifth": 5, "5th": 5, "five": 5, "5": 5,
}

# Highest-frequency ASR / homophone repairs (compiled once at import).
_ASR_PAIRS: Tuple[Tuple[str, str], ...] = (
    (r"\byou\s+tube\b", "youtube"),
    (r"\byt\b", "youtube"),
    (r"\bwhats?\s*app\b", "whatsapp"),
    (r"\bwhatspp\b", "whatsapp"),
    (r"\bgov\s+in\b", "gov.in"),
    (r"\bscrawl\b", "scroll"),
    (r"\bscrol+\b", "scroll"),
    (r"\bseddings\b", "settings"),
    (r"\bsetting'?s\b", "settings"),
    (r"\bvolumn\b", "volume"),
    (r"\bmutes?\b", "mute"),
    (r"\bscreensht\b", "screenshot"),
    (r"\bscreen\s+shots?\b", "screenshot"),
    (r"\bwhats\b", "what is"),
    (r"\bwhat'?s\b", "what is"),
    (r"\bit'?s\b", "it is"),
    (r"\bi'?m\b", "i am"),
    (r"\bopan\b", "open"),
    (r"\barogya\s+seatu\b", "aarogya setu"),
    (r"\baarogya\s+seatu\b", "aarogya setu"),
    (r"\baarogya\s+setu\b", "aarogya setu"),
    (r"\baarogya\s+setup\b", "aarogya setu"),
    (r"\barogya\s+setup\b", "aarogya setu"),
    (r"\btask\s+manger\b", "task manager"),
    (r"\bthe\s+task\s+manager\b", "task manager"),
    (r"\baid\s+of\s+draham\b", "link"),
    # Devanagari phonetic normalization for Indian language commands
    (r"नोटपैड", "notepad"),
    (r"कैलकुलेटर", "calculator"),
    (r"कैल्क", "calc"),
    (r"क्रोम", "chrome"),
    (r"एज", "edge"),
    (r"यूट्यूब", "youtube"),
    (r"व्हाट्सएप", "whatsapp"),
    (r"व्हाट्सऐप", "whatsapp"),
    (r"गूगल", "google"),
    (r"खोलो", "kholo"),
    (r"खोल", "khol"),
    (r"चलाओ", "chalao"),
    (r"स्क्रीनशॉट", "screenshot"),
    (r"आवाज़|आवाज", "aawaz"),
    (r"वॉल्यूम", "volume"),
    (r"बढ़ाओ|बढाओ|तेज़|तेज", "badhao"),
    (r"कम", "kam"),
    (r"करो|करदो", "karo"),
    (r"बंद", "band"),
    (r"म्यूट", "mute"),
    (r"समय|टाइम", "samay"),
    (r"बताओ|बताइए", "batao"),
    (r"तारीख|तारीख़|डेट", "taareekh"),
    (r"नमस्ते|नमस्कार|प्रणाम", "namaste"),
    (r"हेलो|हैलो|हेल्लो", "hello"),
    (r"इरिस|आइरिस", "iris"),
    (r"कैसे|कैसी|कैसा", "kaise"),
    (r"बात", "baat"),
    (r"सकते|सकती|सकता", "sakte"),
    (r"बोल|बोलना", "bol"),
    (r"हिंदी|हिन्दी", "hindi"),
    (r"अलविदा", "alvida"),
    (r"मदद|सहायता", "help"),
)
ASR_COMPILED: Tuple[Tuple[Pattern[str], str], ...] = tuple(
    (re.compile(pat, re.IGNORECASE), repl) for pat, repl in _ASR_PAIRS
)
NON_WORD_RE = re.compile(r"[^\w\s.\-+*/]+")
ORDINAL_NUMBER_RE = re.compile(r"\b(?:number|#)\s*(\d+|one|two|three|four|five)\b")
ORDINAL_WORD_RE = re.compile(r"\b(first|1st|second|2nd|third|3rd|fourth|4th|fifth|5th)\b")
ORDINAL_DIGIT_RE = re.compile(r"\b(\d+)\b")

FILLER_RE = re.compile(
    r"\b(?:uh+|um+|er+|ah+|hmm+|huh+|like|you\s+know)\b",
    re.IGNORECASE,
)
REPEAT_WORD_RE = re.compile(r"\b(\w+)(?:\s+\1\b)+", re.IGNORECASE)
WS_RE = re.compile(r"\s+")
PUNCT_RE = re.compile(r"[,;:?!\"“”‘’()\[\]{}]+")
APOSTROPHE_RE = re.compile(r"['`]")
WAKE_PREFIX_RE = re.compile(
    r"^(?:hey\s+iris|ok\s+iris|hello\s+iris|hi\s+iris|"
    r"wake\s*up(?:\s+(?:up|now|please))?|"
    r"start(?:\s+(?:assistant|listening|up))?|"
    r"hey(?:\s+there)?|"
    r"can\s+you(?:\s+please)?|could\s+you(?:\s+please)?|would\s+you(?:\s+please)?|"
    r"please(?:\s+tell\s+me)?|tell\s+me(?:\s+like)?|tell\s+me|"
    r"show\s+me(?:\s+like)?|show\s+me)\b[,\s]*",
    re.IGNORECASE,
)
TRAILING_POLITE_RE = re.compile(
    r"\b(?:please|kindly|for me)\b|"
    r"\s+on\s+(?:the\s+)?(?:web|browser|internet|edge(?:\.com)?|chrome(?:\.com)?|google)$|"
    r"(?<!\bzoom)\s+in\s+(?:the\s+)?(?:web|internet|browser|edge|chrome)$|"
    r"\s+website$",
    re.IGNORECASE,
)
SPLIT_UTTERANCE_RE = re.compile(
    r"(?<=[.!?])\s+|(?<=,)\s+(?=(?:hi|hey|hello|please|can you|could you|would you|open|search|go to)\b)",
    re.IGNORECASE,
)


@dataclass
class Intent:
    name: str
    params: Dict[str, Any]
    confidence: float = 1.0
    raw_text: str = ""


Extractor = Callable[[re.Match, str, str], Optional[Intent]]


@dataclass
class Rule:
    """One intent family. Higher priority is tried first."""
    name: str
    priority: int
    patterns: List[Pattern[str]]
    extract: Extractor
    kind: str = "exact"  # exact | fuzzy | fallback
    note: str = ""


def _c(pattern: str) -> Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


def _safe_param(value: Optional[str], default: str = "") -> str:
    text = (value or "").strip()
    text = text.replace("\x00", "")
    if ".." in text:
        text = text.replace("..", " ")
    if UNSAFE_PARAM.search(text):
        text = UNSAFE_PARAM.sub(" ", text)
        text = WS_RE.sub(" ", text).strip()
    if len(text) > MAX_PARAM_LEN:
        text = text[:MAX_PARAM_LEN].rstrip()
    return text or default


def _score(kind: str, match: re.Match, text: str) -> float:
    """Meaningful confidence for a future Tier-1 → Tier-2 handoff (< 0.6)."""
    if kind == "fallback":
        return 0.55
    span = match.end() - match.start()
    coverage = span / max(len(text), 1)
    if kind == "fuzzy":
        return 0.72 if coverage < 0.9 else 0.78
    if coverage >= 0.85:
        return 0.98
    if coverage >= 0.5:
        return 0.90
    return 0.82


def _intent(name: str, params: Dict[str, Any], match: re.Match, text: str, raw: str, kind: str) -> Intent:
    return Intent(name=name, params=params, confidence=_score(kind, match, text), raw_text=raw)


def parse_ordinal(blob: str) -> Tuple[str, int]:
    """Normalize 'second' / '2nd' / 'number two' / '2' into nth + remaining target."""
    text = blob.lower()
    nth = 1
    m = ORDINAL_NUMBER_RE.search(text)
    if m:
        token = m.group(1)
        nth = ORDINAL_WORDS.get(token, int(token) if token.isdigit() else 1)
        text = text[: m.start()] + " " + text[m.end() :]
    else:
        m = ORDINAL_WORD_RE.search(text)
        if m:
            nth = ORDINAL_WORDS[m.group(1)]
            text = text[: m.start()] + " " + text[m.end() :]
        else:
            m = ORDINAL_DIGIT_RE.search(text)
            if m and int(m.group(1)) <= 20:
                nth = int(m.group(1))
                text = text[: m.start()] + " " + text[m.end() :]
    target = WS_RE.sub(" ", text).strip()
    return target or "result", nth


def clean_speech_text(text: str) -> str:
    """Central normalization: case, contractions, ASR map, fillers, repeats, punctuation."""
    cleaned = (text or "").lower().strip()
    cleaned = PUNCT_RE.sub(" ", cleaned)
    for pattern, repl in ASR_COMPILED:
        cleaned = pattern.sub(repl, cleaned)
    cleaned = APOSTROPHE_RE.sub("", cleaned)
    cleaned = NON_WORD_RE.sub(" ", cleaned)
    cleaned = FILLER_RE.sub(" ", cleaned)
    cleaned = REPEAT_WORD_RE.sub(r"\1", cleaned)
    cleaned = TRAILING_POLITE_RE.sub(" ", cleaned)
    cleaned = WS_RE.sub(" ", cleaned).strip()

    while True:
        prev = cleaned
        temp = WAKE_PREFIX_RE.sub("", cleaned).strip()
        temp = FILLER_RE.sub(" ", temp)
        temp = TRAILING_POLITE_RE.sub(" ", temp)
        temp = WS_RE.sub(" ", temp).strip()
        if temp:
            cleaned = temp
        else:
            break
        if cleaned == prev:
            break
    return cleaned


def _split_utterance(transcription: str) -> List[str]:
    raw = (transcription or "").strip()
    if not raw:
        return []
    return [p.strip() for p in SPLIT_UTTERANCE_RE.split(raw) if p and p.strip()]


def _open_named(target: str, text: str, raw: str, match: re.Match, kind: str) -> Intent:
    target = _safe_param(target).lower()
    if "whatsapp" in target or "whatsapp" in text:
        if re.search(r"\bwebs?\b|\bbrowser\b|\bsite\b|\bwebsite\b|\bonline\b", text):
            return _intent("OPEN_WEBSITE", {"target": "whatsapp web"}, match, text, raw, kind)
        return _intent("OPEN_APP", {"app_name": "whatsapp"}, match, text, raw, kind)
    if target in ("settings", "setting"):
        return _intent("OPEN_APP", {"app_name": "settings"}, match, text, raw, kind)
    return _intent("OPEN_WEBSITE", {"target": target}, match, text, raw, kind)


def _empty(_m: re.Match, text: str, raw: str, name: str, params: Optional[Dict] = None, kind: str = "exact") -> Intent:
    return _intent(name, params or {}, _m, text, raw, kind)


def _ex_const(name: str, params: Optional[Dict] = None, kind: str = "exact") -> Extractor:
    def _fn(m: re.Match, text: str, raw: str) -> Optional[Intent]:
        return _empty(m, text, raw, name, params, kind)
    return _fn


def _ex_group(name: str, key: str, default: str = "", kind: str = "exact") -> Extractor:
    def _fn(m: re.Match, text: str, raw: str) -> Optional[Intent]:
        value = _safe_param(m.groupdict().get(key) or next((g for g in m.groups() if g), None), default)
        if not value:
            return None
        return _intent(name, {key: value}, m, text, raw, kind)
    return _fn


def _extract_create(m: re.Match, text: str, raw: str) -> Optional[Intent]:
    gd = m.groupdict()
    loc = _safe_param(gd.get("loc") or gd.get("loc2"), "desktop").lower()
    loc = loc.replace("my ", "").strip()
    if loc not in ("desktop", "documents", "iris"):
        loc = "desktop"
    raw_name = _safe_param(gd.get("name") or gd.get("name2") or gd.get("name3"), "note")
    # Clean leading prefix words from raw_name like "named ", "called ", "with name ", "file "
    fname = re.sub(r"^(?:named|called|with\s+(?:the\s+)?name|naam|name|file)\s+", "", raw_name, flags=re.IGNORECASE).strip()
    fname = re.sub(r"\s+(?:on|in)\s+(?:the\s+|my\s+)?(?:desktop|documents|iris)$", "", fname, flags=re.IGNORECASE).strip()
    fname = re.sub(r"\s+file$", "", fname, flags=re.IGNORECASE).strip() or "note"
    if fname.lower() in ("tab", "desktop", "window"):
        return None
    content = _safe_param(gd.get("content"), "")
    content = re.sub(r"^(?:with\s+(?:the\s+)?(?:text|content)\s+|and\s+(?:write|put|add|type)\s+)", "", content, flags=re.IGNORECASE).strip()
    content = re.sub(r"\s+in(?:side)?\s+(?:it|the\s+file)$", "", content, flags=re.IGNORECASE).strip()
    params: Dict[str, Any] = {"filename": fname, "location": loc}
    if content:
        params["content"] = content
    return _intent("CREATE_FILE", params, m, text, raw, "exact")


def _extract_mouse_click(m: re.Match, text: str, raw: str) -> Optional[Intent]:
    t = text.lower()
    return _intent("CLICK_AT_MOUSE", {"double": "double" in t, "right": "right" in t}, m, text, raw, "exact")


def _extract_describe_screen(m: re.Match, text: str, raw: str) -> Optional[Intent]:
    return _intent("READ_SCREEN", {}, m, text, raw, "exact")


def _extract_what_is_open(m: re.Match, text: str, raw: str) -> Optional[Intent]:
    return _intent("WHAT_IS_OPEN", {}, m, text, raw, "exact")


def _extract_list_files(m: re.Match, text: str, raw: str) -> Optional[Intent]:
    gd = m.groupdict()
    loc = gd.get("location") or gd.get("location2") or gd.get("location3") or "desktop"
    return _intent("LIST_FILES", {"location": loc.lower().strip()}, m, text, raw, "exact")


def _extract_list_installed_apps(m: re.Match, text: str, raw: str) -> Optional[Intent]:
    gd = m.groupdict()
    q = _safe_param(gd.get("query") or gd.get("query2") or "")
    return _intent("LIST_INSTALLED_APPS", {"search_query": q}, m, text, raw, "exact")


def _extract_click(name: str) -> Extractor:
    def _fn(m: re.Match, text: str, raw: str) -> Optional[Intent]:
        gd = m.groupdict()
        blob = _safe_param(gd.get("target2") or gd.get("target"))
        if not blob:
            return None
        if blob.lower() in ("tab", "enter", "space", "shift", "ctrl", "alt", "escape", "backspace", "delete"):
            return None

        # Detect mouse pointer keywords inside target
        if re.search(r"\b(?:where\s+(?:the\s+)?mouse\s+is(?:\s+pointing)?|here|at\s+cursor|current\s+position)\b", blob, flags=re.IGNORECASE):
            t = text.lower()
            return _intent("CLICK_AT_MOUSE", {"double": "double" in t, "right": "right" in t}, m, text, raw, "exact")

        # Strip relative clauses like "that is open that is X", "on the screen of X", "that is there"
        clean_blob = blob
        if re.search(r"\b(?:that\s+is\s+open\s+that\s+is|on\s+the\s+screen\s+of)\s+\S+", clean_blob, flags=re.IGNORECASE):
            clean_blob = re.sub(r"^(?:(?:the\s+)?link\s+)?(?:that\s+is\s+open\s+that\s+is|on\s+the\s+screen\s+of)\s+", "", clean_blob, flags=re.IGNORECASE).strip()
        clean_blob = re.sub(r"\bthat\s+is\s+(?:there|present|on\s+(?:the\s+)?screen)\b", "", clean_blob, flags=re.IGNORECASE).strip()
        clean_blob = re.sub(r"[.?!,]+$", "", clean_blob).strip()

        target, nth = parse_ordinal(clean_blob or blob)
        target = _safe_param(target, "result")
        params: Dict[str, Any] = {"target": target}
        if name == "CLICK_ELEMENT":
            params["nth"] = nth
        return _intent(name, params, m, text, raw, "fuzzy")
    return _fn


def _extract_type_send(m: re.Match, text: str, raw: str) -> Optional[Intent]:
    content = _safe_param(m.group("text") or (m.lastindex and m.group(m.lastindex)))
    if not content:
        return None
    return _intent("TYPE_AND_SEND", {"text": content}, m, text, raw, "exact")


def _extract_compound(m: re.Match, text: str, raw: str) -> Optional[Intent]:
    open_tgt = _safe_param(m.group("open"))
    typed = _safe_param(m.group("text"))
    if not open_tgt or not typed:
        return None
    return _intent(
        "COMPOUND_OPEN_AND_TYPE",
        {"open_target": open_tgt, "text_to_type": typed},
        m, text, raw, "exact",
    )


def _extract_whatsapp_message(m: re.Match, text: str, raw: str) -> Optional[Intent]:
    gd = m.groupdict()
    message = _safe_param(gd.get("message") or gd.get("message2") or "")
    contact = _safe_param(gd.get("contact") or gd.get("contact2") or "")
    if not message or not contact:
        return None
    return _intent(
        "WHATSAPP_MESSAGE",
        {"contact": contact, "message": message},
        m, text, raw, "exact",
    )


QUESTION_MARKERS_RE = re.compile(
    r'\b(?:who|what|where|why|how|when|which|kaun|kya|kahan|kab|kisne|kaise|kitna|kitne|batao|explain|meaning|capital|ceo|founder)\b',
    re.IGNORECASE
)


def _extract_search(m: re.Match, text: str, raw: str) -> Optional[Intent]:
    query = _safe_param(m.group("query"))
    if not query:
        return None
    # If the user asked a question (e.g., "Google ke CEO kaun hai", "google what is photosynthesis"),
    # route to KNOWLEDGE_QUERY so it is spoken directly without opening browser tabs
    if QUESTION_MARKERS_RE.search(query) or QUESTION_MARKERS_RE.search(text):
        return _intent("KNOWLEDGE_QUERY", {"query": text, "full_text": text}, m, text, raw, "exact")
    if text.startswith("compare"):
        query = _safe_param(text)
    return _intent("SEARCH_WEB", {"query": query}, m, text, raw, "exact")


def _extract_knowledge(m: re.Match, text: str, raw: str) -> Optional[Intent]:
    gd = m.groupdict()
    query = _safe_param(gd.get("query") or gd.get("query2") or text, text)
    return _intent("KNOWLEDGE_QUERY", {"query": query, "full_text": text}, m, text, raw, "exact")


def _extract_open_site(m: re.Match, text: str, raw: str) -> Optional[Intent]:
    return _open_named(m.group("target"), text, raw, m, "exact")


def _extract_open_app(m: re.Match, text: str, raw: str) -> Optional[Intent]:
    app = _safe_param(m.groupdict().get("app") or "settings").lower()
    if app in ("settings", "setting"):
        app = "settings"
    if not app:
        return None
    # If user explicitly asked for web version of an app (e.g. "open whatsapp web", "whatsapp webs for me")
    if "whatsapp" in app or "whatsapp" in text:
        if re.search(r"\bwebs?\b|\bbrowser\b|\bsite\b|\bwebsite\b|\bonline\b", text):
            return _intent("OPEN_WEBSITE", {"target": "whatsapp web"}, m, text, raw, "exact")
    return _intent("OPEN_APP", {"app_name": app}, m, text, raw, "exact")


def _extract_open_fallback(m: re.Match, text: str, raw: str) -> Optional[Intent]:
    target = _safe_param(m.group("target"))
    if not target:
        return None
    lowered = target.lower()
    if "whatsapp" in lowered or "whatsapp" in text:
        if re.search(r"\bwebs?\b|\bbrowser\b|\bsite\b|\bwebsite\b|\bonline\b", text):
            return _intent("OPEN_WEBSITE", {"target": "whatsapp web"}, m, text, raw, "exact")
    if lowered in ("settings", "setting"):
        return _intent("OPEN_APP", {"app_name": "settings"}, m, text, raw, "exact")
    if re.fullmatch(KNOWN_APPS, lowered):
        return _intent("OPEN_APP", {"app_name": lowered}, m, text, raw, "fuzzy")
    return _intent("OPEN_WEBSITE", {"target": target}, m, text, raw, "fallback")


def _extract_gov(m: re.Match, text: str, raw: str) -> Optional[Intent]:
    return _intent("OPEN_WEBSITE", {"target": "gov.in"}, m, text, raw, "exact")


def _extract_greeting(m: re.Match, text: str, raw: str) -> Optional[Intent]:
    return _intent("GREETING", {"original": text}, m, text, raw, "exact")


def _extract_find(m: re.Match, text: str, raw: str) -> Optional[Intent]:
    q = _safe_param(m.group("query"))
    if not q:
        return None
    return _intent("BROWSER_FIND_ON_PAGE", {"query": q}, m, text, raw, "exact")


def _extract_fill(m: re.Match, text: str, raw: str) -> Optional[Intent]:
    val = _safe_param(m.group("text"))
    if not val:
        return None
    return _intent("FORM_FILL_FIELD", {"text": val}, m, text, raw, "exact")


def _extract_type(m: re.Match, text: str, raw: str) -> Optional[Intent]:
    content = _safe_param(m.group("text"))
    if not content or content.startswith("and send"):
        return None
    return _intent("TYPE_TEXT", {"text": content}, m, text, raw, "fuzzy")


# --- Rule table (priority documented; most frequent commands sit in the 80–90 band) ---
RULES: List[Rule] = [
    Rule("EXIT_ASSISTANT", 100, [_c(rf"\b(?:goodbye|bye|alvida|stop\s+listening)\b|\b(?:iris|assistant)\s+band\s+{HI_VERB}\b|\bquit\b(?!\s+(?:tab|window))|\bexit\b(?!\s+(?:tab|window))")], _ex_const("EXIT_ASSISTANT")),
    Rule("LOCK_SCREEN", 96, [_c(rf"\b(?:lock\s+(?:the\s+)?(?:computer|screen|workstation|pc)|(?:computer|screen)\s+lock\s+{HI_VERB}|screen\s+lock\s+{HI_VERB})\b")], _ex_const("LOCK_SCREEN")),
    Rule(
        "SCREENSHOT",
        95,
        [
            _c(
                rf"\b(?:take\s+(?:a\s+)?(?:screen\s*shot|screenshot|snap|picture\s+of\s+(?:the\s+)?screen)|"
                rf"capture\s+(?:the\s+)?(?:screen|whole\s+page|full\s+screen|entire\s+screen|desktop|page)|"
                rf"(?:screen\s*shot|screenshot)(?:\s+(?:lo|le\s+lo|kheencho|kheecho|khincho|karo))?|"
                rf"ek\s+screenshot(?:\s+le\s+lo|\s+lo)?|"
                rf"save\s+(?:a\s+)?(?:screen\s*shot|screenshot))\b"
                rf"(?:\s+(?:of\s+)?(?:the\s+)?(?:whole\s+page|full\s+screen|entire\s+screen|whole\s+screen|screen|page|desktop))?"
            )
        ],
        _ex_const("SCREENSHOT")
    ),
    Rule("VOLUME_UP", 90, [_c(rf"\b(?:volume\s+up|increase\s+volume|raise\s+volume|turn\s+up\s+(?:the\s+)?volume|louder|aawaz\s+badhao|awaz\s+badhao|volume\s+badhao|aawaz\s+tez\s+{HI_VERB})\b")], _ex_const("VOLUME_UP", {"steps": 3})),
    Rule("VOLUME_DOWN", 90, [_c(rf"\b(?:volume\s+down|decrease\s+volume|lower\s+volume|turn\s+down\s+volume|softer|quieter|aawaz\s+kam\s+{HI_VERB}|volume\s+kam\s+{HI_VERB})\b")], _ex_const("VOLUME_DOWN", {"steps": 3})),
    Rule("VOLUME_MUTE", 90, [_c(rf"\b(?:(?:un)?mute(?:\s+volume)?|silence\s+audio|aawaz\s+band\s+{HI_VERB}|mute\s+{HI_VERB})\b")], _ex_const("VOLUME_MUTE")),
    Rule("SYSTEM_RAM", 88, [_c(r"\b(?:how\s+much\s+)?(?:ram|memory)\b.*\b(?:occupied|used|free|available|left|consumed|usage|status|kitna|kitni)\b|\b(?:check\s+(?:the\s+)?(?:ram|memory)|ram\s+usage|memory\s+usage|how\s+much\s+ram)\b")], _ex_const("SYSTEM_RAM")),
    Rule("SYSTEM_BATTERY", 88, [_c(r"\b(?:how\s+much\s+)?(?:battery|power)\s*(?:percentage|status|level|remaining|life|is\s+left|kitni|kitna|bachi)\b")], _ex_const("SYSTEM_BATTERY")),
    Rule("SYSTEM_CPU", 88, [_c(r"\b(?:cpu|processor)\s*(?:usage|utilization|load|percentage|status|kitna|load\s+kitna)\b")], _ex_const("SYSTEM_CPU")),
    Rule("SYSTEM_TIME", 88, [_c(r"\b(?:what\s+is\s+the\s+time|what\s+time\s+is\s+it|current\s+time|time\s+kya|samay\s+kya|waqt\s+kya|time\s+batao|samay\s+batao|waqt\s+batao)\b")], _ex_const("SYSTEM_TIME")),
    Rule("SYSTEM_DATE", 88, [_c(r"\b(?:what\s+is\s+(?:the\s+)?(?:today'?s?\s+)?date|what\s+day\s+is\s+it|today'?s?\s+date|date\s+kya|taareekh\s+kya|date\s+batao|taareekh\s+batao)\b")], _ex_const("SYSTEM_DATE")),
    Rule("BROWSER_SCROLL_TOP", 87, [_c(rf"\b(?:scroll\s+to\s+top|go\s+to\s+top|top\s+of\s+page|sabse\s+upar\s+(?:jao|{HI_VERB}))\b")], _ex_const("BROWSER_SCROLL_TOP"), note="More specific than generic scroll up"),
    Rule("BROWSER_SCROLL_BOTTOM", 87, [_c(rf"\b(?:scroll\s+to\s+bottom|go\s+to\s+bottom|bottom\s+of\s+page|sabse\s+neeche\s+(?:jao|{HI_VERB}))\b")], _ex_const("BROWSER_SCROLL_BOTTOM")),
    Rule("BROWSER_SCROLL_DOWN", 86, [_c(rf"\b(?:scroll\s+down|page\s+down|neeche\s+scroll(?:\s+{HI_VERB})?|scroll\s+{HI_VERB}\s+neeche|neeche\s+jao)\b")], _ex_const("BROWSER_SCROLL_DOWN", {"steps": 1})),
    Rule("BROWSER_SCROLL_UP", 86, [_c(rf"\b(?:scroll\s+up|page\s+up|upar\s+scroll(?:\s+{HI_VERB})?|scroll\s+{HI_VERB}\s+upar|upar\s+jao)\b")], _ex_const("BROWSER_SCROLL_UP", {"steps": 1})),
    Rule("BROWSER_ZOOM_IN", 86, [_c(rf"\b(?:zoom\s+in(?:\s+browser)?|zoom\s+badao|bada\s+dikhao)\b")], _ex_const("BROWSER_ZOOM_IN")),
    Rule("BROWSER_ZOOM_OUT", 86, [_c(rf"\b(?:zoom\s+out(?:\s+browser)?|zoom\s+kam\s+{HI_VERB}|chhota\s+dikhao)\b")], _ex_const("BROWSER_ZOOM_OUT")),
    Rule("BROWSER_ZOOM_RESET", 86, [_c(rf"\b(?:reset\s+zoom|normal\s+zoom|default\s+zoom|zoom\s+reset(?:\s+{HI_VERB})?)\b")], _ex_const("BROWSER_ZOOM_RESET")),
    Rule(
        "KNOWLEDGE_QUERY",
        84,
        [
            # English standard question prefixes
            _c(r"^(?:what\s+(?:is|are|was|were|happens|did)|who\s+(?:is|was|are|were)|where\s+(?:is|are|was|were)|why\s+(?:is|are|do|does|did)|how\s+(?:does|do|did|is|are|much|many|to)|when\s+(?:is|was|did)|which\s+(?:is|are)|(?:tell\s+me\s+)?about|explain|define|meaning\s+of|capital\s+of|currency\s+of|population\s+of|price\s+of|weather\s+in)\s+(?P<query>.{1,200})$"),
            # Hindi question suffixes
            _c(r"^(?P<query>.{1,120}?)\s+(?:ke\s+baare\s+mein\s+batao|ke\s+bare\s+me\s+batao|kaise\s+kaam\s+karta\s+hai|kaise\s+hota\s+hai|kisne\s+banaya|kya\s+hota\s+hai|kya\s+hai|kaun\s+hai|kaun\s+hain|kaun\s+h|kaun\s+the|kahan\s+hai|kahan\s+h|kab\s+hua|kab\s+tha|kitna\s+hai|kitne\s+hain|kaisa\s+hai|kaisi\s+hai|batao)$"),
            # Hindi question prefixes
            _c(r"^(?:batao\s+(?:ki\s+)?|mujhe\s+batao\s+(?:ki\s+)?)(?P<query>.{1,150})$"),
            # Direct math queries (e.g. 5 + 5, 20 * 4)
            _c(r"^(?:what\s+is\s+|calculate\s+)?(?P<query>\d+(?:\.\d+)?\s*[\+\-\*\/xX]\s*\d+(?:\.\d+)?(?:\s*[\+\-\*\/xX]\s*\d+(?:\.\d+)?)*)(?:\s+kitna\s+hota\s+hai|\s+kya\s+hoga)?$"),
        ],
        _extract_knowledge,
        note="Direct factual Q&A - answered aloud via voice without opening browser"
    ),
    Rule(
        "SEARCH_WEB",
        83,
        [
            _c(r"^(?:search\s+(?:for|on\s+the\s+web\s+for|the\s+web\s+for|web\s+for|google\s+for)|look\s+up(?:\s+on\s+the\s+web)?|google\s+search)\s+(?P<query>.{1,200})$"),
            _c(r"^google\s+(?P<query>.{1,200})$"),
            _c(r"^search\s+(?!on\s+page\b|in\s+page\b|page\s+for\b)(?P<query>.{1,200})$"),
            _c(rf"\b(?:search|google|dhoondo|dhundo)\s+{HI_VERB}\s+(?P<query>.{{1,200}})$"),
            _c(rf"^(?P<query>.{{1,80}}?)\s+(?:search|dhoondo|dhundo)\s+{HI_VERB}$"),
            _c(r"^(?:web\s+par\s+(?:dhoondo|search\s+karo)|internet\s+par\s+(?:dhoondo|search\s+karo))\s+(?P<query>.{1,120})$"),
        ],
        _extract_search,
        note="Explicit web searches only - takes user to browser"
    ),
    Rule(
        "OPEN_APP",
        83,
        [
            _c(rf"(?:{OPEN_VERB})\s+(?:the\s+)?(?:windows\s+)?(?P<app>{KNOWN_APPS})\b"),
            _c(rf"\b(?P<app>{KNOWN_APPS})\s+(?:{HI_OPEN}|open\s+{HI_VERB})\b"),
        ],
        _extract_open_app,
    ),
    Rule("OPEN_WEBSITE", 82, [
        _c(rf"\b(?:{OPEN_VERB})\s+(?:the\s+)?(?:website\s+)?(?P<target>[a-z0-9-]+(?:\.[a-z0-9-]+)+)\b"),
        _c(rf"\b(?:{OPEN_VERB})\s+(?:the\s+)?(?P<target>{KNOWN_SITES})(?:\.com|\.org)?\b"),
        _c(rf"\b(?P<target>{KNOWN_SITES})\s+(?:{HI_OPEN}|open\s+{HI_VERB})\b"),
        _c(rf"^(?P<target>{KNOWN_SITES})(?:\.com|\.org)?$"),
    ], _extract_open_site),
    Rule("CLICK_AT_MOUSE", 86, [
        _c(r"^(?:(?:double|right)\s+)?click\s+(?:on\s+)?(?:where\s+(?:the\s+)?mouse\s+is(?:\s+pointing)?(?:\s+currently)?|here|at\s+(?:the\s+)?cursor|current\s+position)(?:\s+please)?$"),
        _c(r"^(?:where\s+(?:the\s+)?mouse\s+is(?:\s+pointing)?(?:\s+currently)?)\s+par\s+click\s+karo$"),
        _c(r"^(?:click\s+where\s+(?:the\s+)?mouse\s+is|click\s+here|click\s+at\s+cursor)$"),
    ], _extract_mouse_click, kind="exact", note="Instant click at current cursor coordinates"),
    Rule("READ_SCREEN", 85, [
        _c(r"^(?:what\s+is\s+on\s+(?:my\s+|the\s+)?screen|what\s+am\s+i\s+looking\s+at|read\s+(?:my\s+|the\s+)?screen|summarize\s+(?:my\s+|the\s+)?screen)(?:\s+please)?$"),
        _c(r"^(?:screen\s+(?:par\s+kya\s+hai|padho|batao))$"),
    ], _extract_describe_screen, kind="exact"),
    Rule("WHAT_IS_OPEN", 85, [
        _c(r"^(?:what\s+(?:apps|applications|programs|windows)\s+are\s+open|what\s+is\s+open(?:\s+right\s+now)?|what\s+is\s+running\s+in\s+the\s+background|what\s+is\s+happening\s+in\s+the\s+background)(?:\s+please)?$"),
        _c(r"^(?:background\s+mein\s+kya\s+chal\s+raha\s+hai|kya\s+kya\s+open\s+hai)$"),
    ], _extract_what_is_open, kind="exact"),
    Rule("LIST_FILES", 85, [
        _c(r"^(?:what\s+(?:documents?|files?)\s+does\s+(?:my\s+|the\s+)?(?P<location>desktop|documents?|docs|iris)(?:\s+folder)?\s+contain|what\s+(?:documents?|files?)\s+are\s+(?:in|on)\s+(?:my\s+|the\s+)?(?P<location2>desktop|documents?|docs|iris)(?:\s+folder)?|list\s+(?:the\s+)?(?:documents?|files?)\s+(?:in|on)\s+(?:my\s+|the\s+)?(?P<location3>desktop|documents?|docs|iris)(?:\s+folder)?)(?:\s+please)?$"),
        _c(r"^(?:what\s+is\s+(?:in|on)\s+(?:my\s+|the\s+)?(?P<location>desktop|documents?|docs|iris)(?:\s+folder)?)(?:\s+please)?$"),
        _c(r"^(?:(?:desktop|documents?)\s+(?:folder\s+)?(?:par|mein)\s+(?:kya\s+hai|files\s+batao))$"),
    ], _extract_list_files, kind="exact"),
    Rule("LIST_INSTALLED_APPS", 85, [
        _c(r"^(?:what\s+(?:apps|applications)\s+are\s+installed|what\s+installed\s+apps\s+(?:are\s+there|do\s+i\s+have)|list\s+installed\s+apps|which\s+apps\s+(?:can\s+i\s+open|are\s+available)|what\s+apps\s+can\s+i\s+open)(?:\s+please)?$"),
        _c(r"^(?:search\s+(?:for\s+)?(?:installed\s+)?apps?\s+(?:for\s+)?(?P<query>[a-zA-Z0-9_\s]{2,40})|is\s+(?P<query2>[a-zA-Z0-9_\s]{2,40})\s+installed)(?:\s+please)?$"),
        _c(r"^(?:kaun\s+kaun\s+se\s+apps\s+installed\s+hain|installed\s+apps\s+batao)$"),
    ], _extract_list_installed_apps, kind="exact"),
    Rule("CLICK_ELEMENT", 83, [
        _c(r"^(?:click|tap|open|follow)\s+(?:on\s+)?(?:the\s+)?(?P<target>(?:(?:first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th|next|previous)\s+)?(?:result|search\s+result|link|website\s+link|url)(?:\s+(?:on|in)\s+(?:the\s+)?(?:page|screen|results))?)$"),
        _c(r"^(?:click|tap|open)?\s*(?:on\s+)?(?:the\s+)?(?P<target>link\s+that\s+is\s+being\s+displayed)(?:\s+(?:that\s+is\s+)?(?P<target2>.{1,80}))?$"),
        _c(r"^(?:click|tap|open)\s+(?:on\s+)?(?:the\s+)?(?:first|second|third|1st|2nd|3rd)?\s*(?:link|result)?\s*(?:that\s+is\s+open\s+that\s+is\s+|on\s+(?:the\s+)?screen\s+of\s+)(?P<target>.{2,80}?)$"),
        _c(r"^(?:click|tap|open)\s+(?:on\s+)?(?:the\s+)?(?P<target>(?:first|second|third|1st|2nd|3rd)\s+link)$"),
    ], _extract_click("CLICK_ELEMENT"), kind="exact", note="Outranks OPEN_WEBSITE for screen links and search results"),
    Rule("OPEN_APP", 81, [_c(rf"^(?:{OPEN_VERB})\s+(?:the\s+)?(?:app\s+|application\s+)?(?P<app>{KNOWN_APPS})\b"), _c(r"^(?:open|launch|start)\s+(?:app|application)\s+(?P<app>[a-zA-Z0-9_.-]{1,64})")], _extract_open_app),
    Rule("CREATE_FILE", 80, [
        _c(
            r"^(?:create|make|save|write)\s+(?:a\s+)?(?:new\s+)?"
            r"(?:(?P<name>[\w.\-]+\.(?:txt|md|note|log))(?:\s+file)?|"
            r"(?:\.?txt|text)?\s*(?:file|note|document)"
            r"(?:\s+(?:named|called|with\s+(?:the\s+)?name|naam)\s+(?P<name2>.{1,80}?))?)"
            r"(?:\s+(?:on|in)\s+(?:the\s+|my\s+)?(?P<loc>desktop|documents))?"
            r"(?:\s+(?P<name3>(?!and\s)(?!on\s)(?!in\s).{1,80}?))?"
            r"(?:\s+(?:and\s+)?(?:write|put|add|type|with\s+(?:the\s+)?(?:text|content))\s+(?P<content>.{1,200}?)"
            r"(?:\s+in(?:side)?\s+(?:it|the\s+file))?)?$"
        ),
        _c(
            r"^(?:create|make|save|write)\s+(?:a\s+)?(?:new\s+)?(?:file|note|document)?\s+"
            r"(?:on|in)\s+(?:the\s+|my\s+)?(?P<loc2>desktop|documents)\s+"
            r"(?:(?:named|called|with\s+(?:the\s+)?name|naam|file)\s+)?(?P<name>[\w.\-]+(?:\.(?:txt|md|note|log))?)"
            r"(?:\s+(?:and\s+)?(?:write|put|add|type|with\s+(?:the\s+)?(?:text|content))\s+(?P<content>.{1,200}?)"
            r"(?:\s+in(?:side)?\s+(?:it|the\s+file))?)?$"
        ),
        _c(rf"^(?:(?:desktop\s+par\s+)?(?:file|note)\s+banao(?:\s+naam\s+(?P<name>.{{1,80}}))?|(?P<name2>.{{1,80}})\s+file\s+banao)$"),
    ], _extract_create),
    Rule("BROWSER_NEW_TAB", 78, [_c(r"\b(?:new\s+tab|open\s+(?:a\s+)?new\s+tab|create\s+tab|naya\s+tab)\b")], _ex_const("BROWSER_NEW_TAB")),
    Rule("BROWSER_REOPEN_TAB", 79, [_c(rf"\b(?:reopen\s+tab|restore\s+tab|undo\s+close\s+tab|tab\s+wapas\s+{HI_OPEN})\b")], _ex_const("BROWSER_REOPEN_TAB"), note="Must outrank BROWSER_CLOSE_TAB ('close tab' is a substring)"),
    Rule("BROWSER_CLOSE_TAB", 78, [_c(rf"\b(?:(?<!undo\s)close\s+(?:this\s+)?tab|shut\s+tab|exit\s+tab|tab\s+band\s+{HI_VERB})\b")], _ex_const("BROWSER_CLOSE_TAB"), note="Wins over close window when 'tab' is present"),
    Rule("BROWSER_SWITCH_TAB", 78, [_c(r"\b(?:next\s+tab|switch\s+tab|switch\s+to\s+next\s+tab|agla\s+tab)\b")], _ex_const("BROWSER_SWITCH_TAB", {"direction": "next"})),
    Rule("BROWSER_SWITCH_TAB", 78, [_c(r"\b(?:previous\s+tab|prev\s+tab|switch\s+to\s+previous\s+tab|pichla\s+tab)\b")], _ex_const("BROWSER_SWITCH_TAB", {"direction": "prev"})),
    Rule("BROWSER_REFRESH", 78, [_c(rf"\b(?:refresh|reload)(?:\s+page)?(?:\s+{HI_VERB})?|page\s+refresh\s+{HI_VERB}\b")], _ex_const("BROWSER_REFRESH")),
    Rule("BROWSER_OPEN_HISTORY", 77, [_c(rf"\b(?:open\s+history|browser\s+history|show\s+history|history\s+(?:dikhao|{HI_OPEN}))\b")], _ex_const("BROWSER_OPEN_HISTORY")),
    Rule("BROWSER_OPEN_DOWNLOADS", 77, [_c(rf"\b(?:open\s+downloads|browser\s+downloads|show\s+downloads|downloads\s+(?:dikhao|{HI_OPEN}))\b")], _ex_const("BROWSER_OPEN_DOWNLOADS")),
    Rule("BROWSER_BOOKMARK", 77, [_c(rf"\b(?:bookmark(?:\s+this)?(?:\s+page)?|page\s+bookmark\s+{HI_VERB})\b")], _ex_const("BROWSER_BOOKMARK")),
    Rule("BROWSER_GO_BACK", 77, [_c(r"\b(?:go\s+back|back\s+page|previous\s+page|peeche\s+jao)\b")], _ex_const("BROWSER_GO_BACK")),
    Rule("BROWSER_GO_FORWARD", 77, [_c(r"\b(?:go\s+forward|forward\s+page|next\s+page\s+history|aage\s+jao)\b")], _ex_const("BROWSER_GO_FORWARD")),
    Rule("BROWSER_FULLSCREEN", 77, [_c(r"\b(?:toggle\s+fullscreen|fullscreen\s+mode|full\s+screen\s+browser|poori\s+screen|puri\s+screen)\b")], _ex_const("BROWSER_FULLSCREEN")),
    Rule("BROWSER_FIND_ON_PAGE", 77, [_c(r"^(?:find\s+on\s+page|search\s+on\s+page|find\s+in\s+page|search\s+page\s+for|page\s+par\s+dhoondo)\s+(?P<query>.{1,200})$")], _extract_find),
    Rule("WINDOW_SNAP_LEFT", 76, [_c(rf"\b(?:snap\s+(?:window\s+)?left|left\s+snap(?:\s+{HI_VERB})?)\b")], _ex_const("WINDOW_SNAP_LEFT")),
    Rule("WINDOW_SNAP_RIGHT", 76, [_c(rf"\b(?:snap\s+(?:window\s+)?right|right\s+snap(?:\s+{HI_VERB})?)\b")], _ex_const("WINDOW_SNAP_RIGHT")),
    Rule("WINDOW_TASK_VIEW", 76, [_c(r"\b(?:task\s+view|open\s+task\s+view|show\s+tasks|task\s+view\s+dikhao)\b")], _ex_const("WINDOW_TASK_VIEW")),
    Rule("DESKTOP_SWITCH", 76, [_c(r"\b(?:next\s+desktop|switch\s+(?:to\s+)?next\s+desktop|agla\s+desktop)\b")], _ex_const("DESKTOP_SWITCH", {"direction": "next"})),
    Rule("DESKTOP_SWITCH", 76, [_c(r"\b(?:previous\s+desktop|prev\s+desktop|switch\s+(?:to\s+)?prev(?:ious)?\s+desktop|pichla\s+desktop)\b")], _ex_const("DESKTOP_SWITCH", {"direction": "prev"})),
    Rule("DESKTOP_NEW", 76, [_c(r"\b(?:new\s+desktop|create\s+desktop|naya\s+desktop)\b")], _ex_const("DESKTOP_NEW")),
    Rule("DESKTOP_CLOSE", 76, [_c(rf"\b(?:close\s+desktop|delete\s+desktop|desktop\s+band\s+{HI_VERB})\b")], _ex_const("DESKTOP_CLOSE"), note="More specific than WINDOW_CLOSE / EXIT band karo"),
    Rule("WINDOW_CLOSE", 75, [_c(rf"\b(?:close\s+(?:this\s+)?window|exit\s+window|quit\s+window|shut\s+window|window\s+band\s+{HI_VERB}|ise\s+band\s+{HI_VERB})\b")], _ex_const("WINDOW_CLOSE")),
    Rule("WINDOW_MINIMIZE", 75, [_c(rf"\b(?:minimize(?:\s+window)?(?!\s+all)|hide\s+window|window\s+(?:chhota|minimize)\s+{HI_VERB})\b")], _ex_const("WINDOW_MINIMIZE"), note="Negative lookahead so 'minimize all' reaches SHOW_DESKTOP"),
    Rule("SHOW_DESKTOP", 75, [_c(r"\b(?:show\s+desktop|go\s+to\s+desktop|minimize\s+all|desktop\s+dikhao)\b")], _ex_const("SHOW_DESKTOP")),
    Rule("WINDOW_MAXIMIZE", 75, [_c(rf"\b(?:maximize\s+window|maximize|window\s+bada\s+{HI_VERB})\b")], _ex_const("WINDOW_MAXIMIZE"), note="Dropped overlapping 'full screen' which collided with BROWSER_FULLSCREEN"),
    Rule("WINDOW_SWITCH", 75, [_c(rf"\b(?:switch\s+window|switch\s+app|alt\s+tab|next\s+window|window\s+badlo)\b")], _ex_const("WINDOW_SWITCH")),
    Rule("FORM_NEXT_FIELD", 70, [_c(r"\b(?:press\s+tab|next\s+field|next\s+input|tab\s+key|agla\s+field|tab\s+dabao)\b|^tab$")], _ex_const("FORM_NEXT_FIELD")),
    Rule("FORM_PREV_FIELD", 70, [_c(r"\b(?:previous\s+field|prev\s+field|shift\s+tab|back\s+field|pichla\s+field)\b")], _ex_const("FORM_PREV_FIELD")),
    Rule("FORM_SUBMIT", 70, [_c(rf"\b(?:submit\s+form|press\s+enter|hit\s+enter|enter\s+dabao|form\s+submit\s+{HI_VERB})\b|^enter$|^submit$")], _ex_const("FORM_SUBMIT")),
    Rule("FORM_TOGGLE_CHECKBOX", 70, [_c(r"\b(?:toggle\s+checkbox|check\s+box|press\s+space|hit\s+space|space\s+dabao|select\s+checkbox)\b|^space$")], _ex_const("FORM_TOGGLE_CHECKBOX")),
    Rule("FORM_FILL_FIELD", 70, [_c(r"^(?:fill\s+(?:in\s+)?(?:field|input|box)(?:\s+with)?)\s+(?P<text>.{1,200})$"), _c(rf"^(?:field|input|box)\s+bharo(?:\s+{HI_VERB})?\s+(?P<text>.{{1,200}})$")], _extract_fill),
    Rule("SELECT_ALL", 70, [_c(rf"\b(?:select\s+all(?:\s+text)?|highlight\s+all|sab\s+select\s+{HI_VERB})\b")], _ex_const("SELECT_ALL")),
    Rule("CLEAR_FIELD", 70, [_c(rf"\b(?:clear\s+(?:the\s+)?(?:field|input|text|box)|erase\s+(?:the\s+)?(?:field|input|text)|field\s+khali\s+{HI_VERB})\b")], _ex_const("CLEAR_FIELD")),
    Rule("COPY_TEXT", 70, [_c(rf"\b(?:copy(?:\s+this|\s+that|\s+text)?|copy\s+{HI_VERB})\b")], _ex_const("COPY_TEXT")),
    Rule("PASTE_TEXT", 70, [_c(rf"\b(?:paste(?:\s+this|\s+that|\s+text|\s+here)?|paste\s+{HI_VERB})\b")], _ex_const("PASTE_TEXT")),
    Rule("UNDO_ACTION", 70, [_c(rf"\b(?:undo(?:\s+that|\s+last\s+action|\s+edit)?(?!\s+close\s+tab)|undo\s+{HI_VERB})\b")], _ex_const("UNDO_ACTION"), note="Does not steal 'undo close tab'"),
    Rule("WHATSAPP_MESSAGE", 88, [
        _c(r"^(?:send|text|message|msg)\s+(?P<message>.{1,200}?)\s+to\s+(?P<contact>.{1,80}?)\s+(?:on|in|via)\s+whatsapp$"),
        _c(r"^(?:send|text|message|msg)\s+(?P<message>.{1,200}?)\s+to\s+(?P<contact>.{1,80})\s+on\s+whatsapp\s+web$"),
        _c(r"^whatsapp\s+(?P<contact>.{1,80}?)\s+ko\s+(?P<message>.{1,200}?)\s+bhej(?:o|\s+do)$"),
        _c(r"^(?:send\s+(?:a\s+)?(?:whatsapp|whatsapp\s+web)\s+(?:message\s+)?(?:to\s+)?(?P<contact>.{1,80}?)\s+(?:saying|message|that\s+says?)\s+(?P<message2>.{1,200}))$"),
        _c(r"^(?:on\s+whatsapp\s+)?send\s+(?P<message>.{1,200}?)\s+to\s+(?P<contact>.{1,80})$"),
    ], _extract_whatsapp_message, note="Dedicated WhatsApp messaging — outranks COMPOUND and SEARCH"),
    Rule("COMPOUND_OPEN_AND_TYPE", 85, [_c(r"^(?P<open>open\s+.{1,80}?)\s+and\s+(?:then\s+)?(?:type|write|say|send|text|message|msg)\s+(?P<text>.{1,200})$"), _c(rf"^(?P<open>{HI_OPEN}\s+.{{1,80}}?)\s+aur\s+(?:type|likho|likh|bhej)\s+(?:{HI_VERB}\s+)?(?P<text>.{{1,200}})$")], _extract_compound, note="Must outrank OPEN_APP/OPEN_WEBSITE"),
    Rule("TYPE_AND_SEND", 61, [_c(r"^(?:type|text|send\s+message|write)\s+(?P<text>.{1,200}?)\s+(?:and\s+send(?:\s+it)?|aur\s+bhej\s+do)$"), _c(r"^(?:type\s+and\s+send|write\s+and\s+send)\s+(?P<text>.{1,200})$")], _extract_type_send),
    Rule("SEND_MESSAGE", 60, [_c(rf"\b(?:send\s+message|send\s+it|message\s+bhej\s+do|send\s+{HI_VERB})\b")], _ex_const("SEND_MESSAGE")),
    Rule("TYPE_TEXT", 60, [_c(r"^(?:type|write|enter\s+text)\s+(?P<text>.{1,200})$"), _c(rf"^(?:type|likho|likh)\s+{HI_VERB}\s+(?P<text>.{{1,200}})$")], _extract_type, kind="fuzzy"),
    Rule("MEDIA_PLAY_PAUSE", 55, [_c(r"\b(?:play\s+music|pause\s+music|resume\s+playback|play\s+media|gana\s+bajao|gana\s+roko)\b")], _ex_const("MEDIA_PLAY_PAUSE"), note="Dropped bare 'pause' — collided with unrelated speech"),
    Rule("READ_SCREEN", 52, [_c(r"\b(?:read\s+(?:the\s+)?screen|what\s+is\s+on\s+(?:the\s+)?screen|screen\s+padho|screen\s+dikhao)\b")], _ex_const("READ_SCREEN")),
    Rule("DOUBLE_CLICK_ELEMENT", 51, [_c(r"(?:double\s+click|double\s+tap)\s+(?:on\s+)?(?:the\s+)?(?P<target>.{1,80}?)$"), _c(rf"^(?P<target>.{{1,80}}?)\s+(?:par|pe)\s+(?:do\s+baar\s+click|double\s+click)\s+{HI_VERB}$")], _extract_click("DOUBLE_CLICK_ELEMENT"), kind="fuzzy", note="Must outrank CLICK_ELEMENT"),
    Rule("RIGHT_CLICK_ELEMENT", 51, [_c(r"(?:right\s+click|right\s+tap)\s+(?:on\s+)?(?:the\s+)?(?P<target>.{1,80}?)$"), _c(rf"^(?P<target>.{{1,80}}?)\s+(?:par|pe)\s+right\s+click\s+{HI_VERB}$")], _extract_click("RIGHT_CLICK_ELEMENT"), kind="fuzzy"),
    Rule("HOVER_ELEMENT", 51, [_c(r"(?:hover\s+(?:over|on)|move\s+(?:mouse|cursor)\s+(?:to|over|on))\s+(?:the\s+)?(?P<target>.{1,80}?)$"), _c(rf"^(?P<target>.{{1,80}}?)\s+(?:par|pe)\s+hover\s+{HI_VERB}$")], _extract_click("HOVER_ELEMENT"), kind="fuzzy"),
    Rule("CLICK_ELEMENT", 50, [_c(r"(?:click|tap)\s+(?:on\s+)?(?:the\s+)?(?P<target>.{1,80}?)$"), _c(rf"^(?P<target>.{{1,80}}?)\s+(?:par|pe)\s+(?:click|tap)\s+{HI_VERB}$")], _extract_click("CLICK_ELEMENT"), kind="fuzzy"),
    Rule(
        "GREETING",
        86,
        [
            _c(r"^(?:hello|hi|hey|wake\s*up|start|good\s+morning|good\s+afternoon|good\s+evening|namaste|namaskar|pranam)(?:\s+iris)?$"),
            _c(r"^(?:who\s+are\s+you|what\s+can\s+you\s+do|how\s+are\s+you(?:\s+doing)?|help|aap\s+kaun\s+ho|tum\s+kaun\s+ho|tum\s+kaise\s+ho|aap\s+kaise\s+ho|kaise\s+ho|kya\s+haal\s+hai|kya\s+haal)(?:\s+iris)?$"),
            _c(r"^(?:hello\s+)?(?:iris\s+)?(?:tum\s+kaise\s+ho|aap\s+kaise\s+ho|kaise\s+ho)(?:\s+iris)?$"),
            _c(r"^(?:(?:kya\s+)?(?:aap|tum)\s+)?(?:hindi|hindi\s+mein)(?:\s+baat\s+kar\s+sakte\s+ho|\s+bol\s+sakte\s+ho|\s+aati\s+hai|\s+samajhte\s+ho)(?:\s+iris)?$"),
            _c(r"^(?:can\s+you\s+speak\s+hindi|do\s+you\s+speak\s+hindi|speak\s+in\s+hindi|talk\s+in\s+hindi)$"),
        ],
        _extract_greeting,
    ),
    Rule("OPEN_WEBSITE", 20, [_c(r"^(?:open|launch)\s+(?P<target>.{1,120})$")], _extract_open_fallback, kind="fallback", note="Low confidence; intended Tier-2 handoff"),
    Rule("KNOWLEDGE_QUERY", 15, [_c(r"\b(?:what|who|where|when|why|how|tell|explain|define|meaning|kya|kaun|kaise|batao)\b")], lambda m, t, r: _intent("KNOWLEDGE_QUERY", {"query": _safe_param(t), "full_text": t}, m, t, r, "fallback") if len(t.split()) >= 3 else None, kind="fallback"),
    Rule("SEARCH_WEB", 10, [_c(r"\b(?:compare|versus|vs|difference)\b")], lambda m, t, r: _intent("SEARCH_WEB", {"query": _safe_param(t)}, m, t, r, "fallback") if len(t.split()) >= 3 else None, kind="fallback"),
]

RULES.sort(key=lambda rule: -rule.priority)


def _parse_intent_core(transcription: str, raw_text: Optional[str] = None) -> Intent:
    if raw_text is None:
        raw_text = transcription
    text = clean_speech_text(transcription)
    if not text:
        return Intent(name="UNKNOWN", params={}, confidence=0.0, raw_text=raw_text)

    for rule in RULES:
        for pattern in rule.patterns:
            match = pattern.search(text)
            if not match:
                continue
            intent = rule.extract(match, text, raw_text)
            if intent is None:
                continue
            return intent
    return Intent(name="UNKNOWN", params={"raw": text}, confidence=0.0, raw_text=raw_text)


def parse_intent(transcription: str) -> Intent:
    segments = _split_utterance(transcription)
    if len(segments) > 1:
        found: List[Intent] = []
        for segment in segments:
            intent = _parse_intent_core(segment, transcription)
            if intent.name != "UNKNOWN":
                found.append(intent)
        actionable = [i for i in found if i.name != "GREETING"]
        if actionable:
            last = actionable[-1]
            if last.name == "CLICK_ELEMENT" and last.params.get("target") in ("that", "this", "it", "result"):
                for prev in reversed(actionable[:-1]):
                    if prev.name == "CLICK_ELEMENT" and prev.params.get("target") not in ("that", "this", "it", "result"):
                        last.params["target"] = prev.params["target"]
                        if "nth" in prev.params:
                            last.params["nth"] = prev.params["nth"]
                        break
            return last
        if found:
            return found[-1]
        return Intent(name="UNKNOWN", params={"raw": clean_speech_text(transcription)}, confidence=0.0, raw_text=transcription)
    return _parse_intent_core(transcription, transcription)
