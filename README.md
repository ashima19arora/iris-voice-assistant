# Iris

**Digital braille for the internet — say it, and it happens.**

Iris is a voice-first assistant built for people the digital world leaves out — blind and low-vision users, and the much larger group of low-literacy, rural, and elderly users. It sits at the OS level and lets a person ask for something and have it happen, the way they always could before every essential service moved behind a mouse and a set of eyes.

---

## Table of Contents

- [The Problem](#the-problem)
- [The Idea](#the-idea)
- [Current Build Status](#current-build-status)
- [Architecture](#architecture)
- [Features & Principles](#features--principles)
- [Quick Start & Setup](#quick-start--setup)
- [Voice Commands (Examples)](#voice-commands-examples)
- [How Intent Matching Works](#how-intent-matching-works)
- [Extending Iris](#extending-iris-add-a-new-voice-command)
- [Safety & Sandboxing](#safety--sandboxing)
- [Verification & Tests](#verification--tests)

---

## The Problem

For centuries, the answer to "what if someone can't see the page or hold the book" was Braille — not a translation of books, but a rebuild of the reading interface around a different sense. The internet never got its Braille. Learning, paying bills, booking appointments, raising a complaint — all of it now lives behind a mouse and a set of eyes, with no equivalent adaptation for the people who don't have both.

India has an estimated 26.8 million persons with disabilities. Beyond that, 250 million Indian adults have limited literacy and 130 million elderly citizens are counted as digitally illiterate. Different reason, same locked door.

Existing solutions do not cover this well: screen-reader-paired tools assume English fluency and cost real money (JAWS: $95/year and up), Windows' own voice control is English-only and internet-dependent, and none of them check in before acting or admit when something went wrong. Iris is scoped as OS-level rather than document/browser-only, free, and built around confirmation and narration by design.

---

## The Idea

An always-present, hands-free assistant for Windows that listens for a wake phrase, takes a spoken command, and executes it: opening apps, navigating sites, filling forms, completing multi-step tasks. It narrates what it is doing as it works, and — critically — checks in before anything irreversible happens, rather than silently acting on a person's behalf.

---

## Current Build Status

**Built, integrated, and verified (170+ tests passing):**
- **Offline speech-to-text, English:** Tested against casual phrasing, filler words, self-correction, and long multi-clause commands (NVIDIA Parakeet TDT 0.6B v2, int8, local via `onnx-asr`).
- **Wake-word & Lifecycle:** "hey iris" / "hi iris" / "hello iris" / "wake up", automatic inactivity sleep after 45 seconds of silence, and exit triggers.
- **Intent Parsing Engine (`actions/intent_parser.py`):** Rule-based offline parsing with polite filler normalization, multi-step compound intent splitting, and conversational antecedent resolution.
- **OS & Desktop Execution (`actions/`):** Full support for app launching, volume/media, window controls, screenshotting, file operations, system metrics (RAM/CPU), and browser automation.
- **Vision & Screen Understanding (`actions/screen_understanding.py`):** Windows UI Automation tree inspection via `uiautomation`, active window detection (`win32gui`), and layout-aware OCR (`rapidocr-onnxruntime`) with mouse pointer click targeting (`click_at_mouse_position`).
- **Safety, Security & Audit (`actions/security/`):** 3-tier intent classification (Safe, Confirmation Required, Blocked), allowlisted write paths, URL sanitization, and tamper-resistant audit logs.
- **Spoken Feedback & Narration (`actions/feedback.py`):** Concise one-liner voice feedback with speech deduplication and confirmation gates for destructive actions.

**Under active roadmap:**
- Hindi / code-switched multi-lingual speech models
- Task templates for specific high-friction e-governance and banking services

---

## Architecture

Windows-only for now; wake-word activation (not push-to-talk) was chosen specifically because primary users cannot reliably rely on a physical button press, and it's what "always-present, hands-free" requires.

```
Mic input
  → Wake word detection ("Hey Iris")
  → Speech capture
  → ASR / transcription  (NVIDIA Parakeet TDT 0.6B v2, int8, local via onnx-asr, offline)
  → Intent parsing (Rule-based normalization & compound splitter)
  → Action mapping & Security tier validation (Safe / Confirm / Blocked)
  → Execution (OS/app-level: open app, click, navigate, fill field, UI automation)
  → TTS narration of each step
  → Confirmation gate (if irreversible)
  → Result spoken back
```

Always-on in parallel: stop-word detection and a manual mic-mute toggle, independent of the wake word.

---

## Features & Principles

- **Spoken confirmation before anything irreversible:** Low-literacy users tend to trust AI output uncritically rather than verify it — confirmation gates are the structural fix transcription accuracy alone cannot provide.
- **Narrated execution:** Speaks each step as it happens, answering the de-skilling concern blind users raised themselves — keeps the user oriented instead of turning execution into a black box.
- **Directed interruption ("stop"/"wait"):** A single always-listened-for stop-word captures immediate user intent without unstable real-time barge-in overhead.
- **Manual mic-mute + visible listening state:** Independent of the wake word — a real privacy control for user trust.
- **Failure honesty:** States clearly when something cannot be done or was not recognized, rather than hallucinating success.

---

## Quick Start & Setup

### Requirements

- Windows 10/11
- Python 3.10+
- A working microphone

### Install

```powershell
pip install -r requirements.txt
playwright install chromium
```

### Run Iris

You can start Iris either using npm or directly with Python:

```powershell
# Using the dev runner
npm run dev

# Or directly with Python
python assistant.py
```

Say commands after you hear that Iris is active (or say "Hey Iris").

### Run the speech-to-text diagnostic tool

```powershell
python listen.py
```

---

## Voice Commands (Examples)

- **System & Memory:** "tell me how much RAM used" / "check battery"
- **App Control:** "open settings", "open notepad", "open task manager"
- **Navigation & Web:** "open youtube", "open gov.in", "search for weather in Delhi"
- **File Actions:** "create a note.txt file on desktop"
- **Screen & Vision:** "what is on my screen?", "read what's open", "click here", "click on the first link"
- **Window Management:** "minimize window", "maximize", "scroll down", "volume up"
- **Safety / Lock:** "lock screen"

---

## How Intent Matching Works

`actions/intent_parser.py` is rule-based (regex), fully offline, and deterministically fast. It:
1. Strips polite filler ("please", "can you", "could you kindly").
2. Resolves multi-sentence conversational context ("open google and search news").
3. Matches the targeted intent parameters and returns structured `Intent` objects mapped to validated execution handlers.

---

## Extending Iris (Add a New Voice Command)

Adding a new voice command takes fewer than 5 lines of code:

1. Add a pattern in `actions/intent_parser.py` returning `Intent(name="MY_INTENT", params={...})`.
2. Add the corresponding handler in `actions/registry.py` (`INTENT_HANDLERS`).
3. Set the intent safety tier in `actions/security/policy.py` (`INTENT_TIERS`).
4. If it's a web destination or application, register it in `actions/config.py`.

---

## Safety & Sandboxing

- **File System Sandboxing:** File creations and writes are restricted exclusively to safe user directories (Desktop, Documents, or `~/Iris`).
- **Network Safety:** Browser navigation enforces valid `http`/`https` protocols against suspicious scheme injection.
- **Application Allowlist:** System process spawning is restricted to an approved allowlist of trusted productivity and utility apps.
- **No Insecure Execution:** No `eval()`, `exec()`, or unsanitized shell executions.

---

## Verification & Tests

Run the full automated test suite (covering intent parsing, security policies, context providers, browser actions, and screen :wq
understanding):

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```
