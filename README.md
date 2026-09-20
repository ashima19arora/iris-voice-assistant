# Iris — Digital Braille for the Internet

> A voice-first accessibility layer for the Windows desktop and the browser.
> Say it, and it happens.

[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6?logo=windows&logoColor=white)](https://github.com/ashima19arora/iris-voice-assistant)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

## Table of Contents

- [The Problem](#the-problem)
- [The Idea](#the-idea)
- [Current Build Status](#current-build-status)
- [Architecture](#architecture)
- [Interfaces](#interfaces)
- [Where AWS Fits](#where-aws-fits)
- [Setup](#setup)

---

## The Problem

For centuries, the answer to "what if someone can't see the page or hold the book" was Braille — not a translation of books, but a rebuild of the reading interface around a different sense. The internet never got its Braille. Learning, paying bills, booking a government appointment, filing a complaint, ordering what you need — all of it now lives behind a mouse and a set of eyes, with no equivalent adaptation for the people who don't have both.

India has an estimated **26.8 million** people with disabilities. Beyond that, **250 million** Indian adults have limited literacy, and **130 million** elderly citizens are counted as digitally illiterate — they can speak a request perfectly, but can't reliably read the screen meant to let them make it. Different reason, same locked door.

Existing tools don't close this gap. Screen-reader-paired software assumes English fluency and costs real money — a JAWS license runs $95 a year and up. Windows' own voice control is English-only and needs internet to function. None of them check in before acting on your behalf, and none of them admit when something went wrong.

---

## The Idea

An always-present, hands-free assistant for Windows that listens for a wake phrase (or a right-click push-to-talk on the desktop Orb), takes a spoken command, and executes it: opening apps, navigating sites, filling forms, completing multi-step tasks. It narrates what it's doing as it works, and — critically — checks in before anything irreversible happens, rather than silently acting on a person's behalf.

Iris responds in Hindi as well as English for common commands and spoken replies, alongside full English support.

---

## Current Build Status

**Built and tested:**
- Offline speech-to-text, English — NVIDIA Parakeet TDT 0.6B (int8), on-device
- Wake-word activation and right-click push-to-talk
- Continuous listening, automatic sleep on inactivity, graceful exit
- Direct command execution: opening applications, navigating and controlling a browser, reading and clicking on-screen elements, system-level actions (volume, windows, screenshots)
- Spoken responses in English and Hindi for supported commands
- Windows Desktop Orb and Chrome browser extension

**Not yet fully verified:**
- Full Hindi speech recognition robustness across varied, natural phrasing — supported for common commands, still being tested against the same real-speech standard used for English
- Task templates for specific high-friction services (e.g. Aadhaar appointment booking) as a fully guided, multi-step flow
- Text-to-speech reliability in all execution paths

---

## Architecture

```
Mic input
  → Wake word detection / push-to-talk
  → Speech capture
  → ASR / transcription  (NVIDIA Parakeet TDT 0.6B, int8, local via onnx-asr, offline)
  → Fast intent match
      ├─ matched   → security check
      └─ ambiguous → AI reasoning (AWS Strands + Bedrock / OpenRouter) → security check
  → Security check (AWS Cedar)
  → Execute
  → Log (Amazon DynamoDB)
  → Spoken result (Amazon Polly / local TTS fallback)
```

Simple, exact commands are handled fast and entirely offline. Only genuinely ambiguous requests escalate to AI reasoning. Every command, on either path, passes through the same security check before it's allowed to execute.

---

## Interfaces

**Windows Desktop Orb** — a floating, always-on-top overlay. Wake word or right-click-and-hold to speak. Controls the full OS: apps, files, volume, windows, screenshots.

**Chrome extension** — an in-page floating orb for browser-only actions (scroll, read page, click). For OS-level commands, it forwards to the Desktop Orb's local bridge if it's running.

**Command line** — `listen.py` for isolated speech-to-text testing, `assistant.py` for the full loop.

---

## Where AWS Fits

| Service | Solves | How |
|---|---|---|
| AWS Cedar | Security rules scattered across ad-hoc checks | Local, deterministic policy engine; evaluates every command before execution |
| AWS Strands Agents | No structured way for AI to reliably call the right action | Exposes real callable tools to the reasoning layer |
| Amazon Bedrock | Commands too ambiguous for fixed pattern matching | Foundation-model reasoning for open-domain questions and disambiguation |
| Amazon DynamoDB | An audit trail that lived only in memory | Permanent, queryable log of every command, decision, and latency |
| Amazon Polly | Flat, robotic voice output | Neural voice synthesis, English and Hindi |
| Amazon Translate | No path to other languages | Voice-to-voice translation across 75+ languages |
| Amazon Comprehend | No sense of user frustration | Sentiment detection on spoken input |
| AWS Amplify | No public place to try it | Hosts the live demo site |
| AWS SAM | Manual, error-prone infra setup | Declares the backend as code, one command, zero cost locally |

The entire backend is declared as code with AWS SAM, runnable locally via LocalStack at zero cost, or deployed to real AWS.

---

## Setup

### Requirements
- Windows 10 or 11
- Python 3.10+
- Node.js 18+ (for the Desktop Orb)
- A microphone

### Install

```powershell
pip install -r requirements.txt
playwright install chromium
npm install
cd Orb
npm install
cd ..
```

### Configure

Copy `.env.example` to `.env` and fill in your own values. Iris runs without any keys for core commands — keys unlock smarter reasoning (OpenRouter) and cloud voice/logging (AWS).

```powershell
copy .env.example .env
```

### Run

```powershell
npm run orb
```

A floating orb should appear. First launch loads the speech model into memory — this can take 30–90 seconds and is expected.

CLI-only, no Orb UI:

```powershell
python assistant.py
```

### Test

```powershell
python -m pytest tests -q
```