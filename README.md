# Iris

**Digital braille for the internet — say it, and it happens.**

Iris is a voice-first assistant built for people the digital world leaves out — blind and low-vision users, and the much larger group of low-literacy, rural, and elderly users. It sits at the OS level and lets a person ask for something and have it happen, the way they always could before every essential service moved behind a mouse and a set of eyes.

This README reflects the project as it currently stands: foundation layer complete, higher layers under active construction. Status is called out explicitly throughout, not overclaimed.

---

## Table of Contents

- [The Problem](#the-problem)
- [The Idea](#the-idea)
- [Current Build Status](#current-build-status)
- [Architecture](#architecture)
- [Features — Planned and Reasoning](#features--planned-and-reasoning)
- [Setup](#setup)

---

## The Problem

For centuries, the answer to "what if someone can't see the page or hold the book" was Braille — not a translation of books, but a rebuild of the reading interface around a different sense. The internet never got its Braille. Learning, paying bills, booking appointments, raising a complaint — all of it now lives behind a mouse and a set of eyes, with no equivalent adaptation for the people who don't have both.

India has an estimated 26.8 million persons with disabilities. Beyond that, 250 million Indian adults have limited literacy and 130 million elderly citizens are counted as digitally illiterate. Different reason, same locked door.

Existing solutions do not cover this well: screen-reader-paired tools assume English fluency and cost real money (JAWS: $95/year and up), Windows' own voice control is English-only and internet-dependent, and none of them check in before acting or admit when something went wrong. Iris is scoped as OS-level rather than document/browser-only, free, and built around confirmation and narration by design — see [Features](#features--planned-and-reasoning) below.

---

## The Idea

An always-present, hands-free assistant for Windows that listens for a wake phrase, takes a spoken command, and executes it: opening apps, navigating sites, filling forms, completing multi-step tasks. It narrates what it is doing as it works, and — critically — checks in before anything irreversible happens, rather than silently acting on a person's behalf.

---

## Current Build Status

**Built and tested:**
- Offline speech-to-text, English — tested against casual phrasing, filler words, self-correction, and long multi-clause commands
- Wake-word detection: "hey iris" / "hi iris" / "hello iris" / "wake up"
- Automatic inactivity sleep after 45 seconds of silence
- Exit on "exit" / "goodbye" / "bye"

**Not yet built:**
- Intent parsing, action mapping, and OS-level execution
- Text-to-speech narration
- Confirmation gates before irreversible actions
- Hindi / code-switched support
- Task templates for specific high-friction services

---

## Architecture

Windows-only for now; wake-word activation (not push-to-talk) was chosen specifically because the primary users can't reliably rely on a physical button press, and it's what "always-present, hands-free" requires.

```
Mic input
  → Wake word detection
  → Speech capture
  → ASR / transcription  (NVIDIA Parakeet TDT 0.6B v2, int8, local via onnx-asr, offline, Windows)
  → Intent parsing
  → Action mapping
  → Execution (OS/app-level: open app, click, navigate, fill field)
  → TTS narration of each step
  → Confirmation gate (if irreversible)
  → Execute or await confirmation
  → Result spoken back
```

Always-on in parallel: stop-word detection and a manual mic-mute toggle, independent of the wake word.

Implemented so far: everything through transcription, plus the wake/sleep/exit logic around it. Intent parsing onward is planned, not yet built.

---

## Features — Planned and Reasoning

- **Spoken confirmation before anything irreversible.** Low-literacy users tend to trust AI output uncritically rather than verify it — confirmation is the structural fix transcription accuracy alone can't provide.
- **Narrated execution.** Speaks each step as it happens; answers the de-skilling concern blind users raised themselves — keeps the person oriented instead of the task vanishing into a black box.
- **Directed interruption ("stop"/"wait").** A single always-listened-for stop-word, not full conversational barge-in — captures most of the practical value without the (genuinely unsolved) engineering cost of real-time interrupt handling.
- **Manual mic-mute + visible listening state**, independent of the wake word — a real privacy control for a user group already prone to over-trusting the system.
- **Failure honesty.** Says when something didn't work instead of assuming success — confidently wrong actions damage trust far more than an honest "I didn't catch that," and low-literacy users are least equipped to catch a wrong action themselves.
- **Hindi / code-switched support, offline** — see [Current Build Status](#current-build-status).
- **Task templates** for a small number of concrete, high-friction services (e.g. an appointment-booking flow), demoable end-to-end rather than only generic open/click commands.

---

## Setup

Covers what currently exists in this repository.

### Requirements

- Python 3.10+
- A working microphone
- Windows

### Install

```
pip install -r requirements.txt
```

### Run the speech-to-text diagnostic tool

```
python listen.py
```

### Run the assistant loop

**Not yet functional standalone** — imports an `actions` package for intent parsing and execution that hasn't been added to this repo yet; will raise an import error until that layer is built. Included now so the wake/sleep/exit logic is visible and reviewable ahead of that work.

```
python assistant.py
```