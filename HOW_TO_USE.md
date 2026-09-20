# How to use Iris — Chrome extension and local setup

This is the user guide for **Iris v1.0.0**. Iris has two parts that work together:

| Product | What it is | Needs a cloud API key? |
|---|---|---|
| **Desktop Orb** (Windows) | Full voice OS: apps, files, volume, Task Manager, spoken Q&A | **No** for everyday commands. Optional keys only improve voice quality and open-ended questions. |
| **Chrome extension** | Mic + orb **on the webpage**: scroll, read page, click-to-speak | **No** Iris key. Uses Chrome’s built-in speech. For **desktop** actions (open Notepad, create a file), the Desktop Orb must also be running. |

---

## 1. Local setup (Desktop Orb — recommended)

Use this if you want Iris to control Windows, speak answers, and open sites in your real browser.

### Requirements

- Windows 10 or 11
- Python 3.10+ (3.13 is fine)
- Node.js 18+ (for `npm run orb`)
- A microphone
- Internet **once** so the speech model can download; after that, listening can work offline

### Install

Open PowerShell in the project folder:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm install
cd Orb
npm install
cd ..
```

Optional (only if you use Playwright browser automation in tests):

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
```

### Run

From the **repo root**:

```powershell
npm run orb
```

A floating orb should appear. Allow the microphone if Windows asks.

CLI-only (no orb UI):

```powershell
npm run cli
```

### First launch (normal, not a bug)

The first time, NVIDIA Parakeet speech-to-text loads into memory. That can take **30–90 seconds**. Later launches are faster. This is local compute, not an API round-trip.

### Commands that work with **no API keys**

Say (or type in the Orb):

- “What is the capital of France?” — spoken one-liner, **no browser**
- “Bharat ki rajdhani kya hai?” — Hindi answer, **no browser**
- “Search web for space exploration” — announces, then opens Google
- “Open Task Manager” / “Open settings” / “Open YouTube”
- “Create a text.txt file on my desktop and write hello in it”
- “How much RAM is used?” / “Volume up” / “Scroll down”

Speech: local engine (pyttsx3 / gTTS fallback).  
Understanding: local regex fast path for these commands.

### Optional keys (not required)

Put these in a `.env` file in the repo root **only if you have them**. Never commit `.env`.

| Variable | What you gain |
|---|---|
| `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` + `AWS_DEFAULT_REGION` | Amazon Polly (Joanna / Aditi) instead of local TTS; optional DynamoDB/CloudWatch |
| `OPENROUTER_API_KEYS` | Smarter answers when the phrase is not a known command |

Without keys, Iris still runs. Open-ended “do whatever is on this page” may be weaker; core commands above still work.

### Stop

Close the Orb window, or press `Ctrl+C` in the terminal.

---

## 2. Chrome extension

The extension lives in `iris-extension/`. It is **not** on the Chrome Web Store in this release — you load it unpacked (or from the release zip).

### Install from a GitHub Release zip

1. Download **`iris-browser-extension-v1.0.0.zip`** from the release.
2. Unzip it to a folder (keep `manifest.json` at the top of that folder).
3. Chrome → `chrome://extensions`
4. Turn on **Developer mode** (top right).
5. **Load unpacked** → select the unzipped `iris-extension` folder.
6. Pin Iris on the toolbar.

### Install from this repo (developers)

Same as above, but Load unpacked → `iris-extension/` in the cloned repo.

### Grant the microphone

1. Click the Iris icon.
2. If you see **Allow Mic**, click it and allow Chrome to use the mic.
3. Click the orb and speak, or type a command.

Shortcut: `Ctrl+Shift+Space` toggles the in-page floating orb.

### What the extension can do **by itself** (no Desktop Orb)

On the **current tab**:

- Listen and type/speak
- Scroll up / down / top / bottom
- Read the page title / selection (Chrome TTS)
- Highlight links

No AWS or OpenRouter key is required.

### What needs Desktop Orb running

If you say “open Task Manager”, “create a file on desktop”, or similar **Windows** commands, the extension forwards them to:

`http://127.0.0.1:7878`

So:

1. Start **`npm run orb`** first (bridge on port **7878**).
2. Then use the extension on a webpage.

If the Orb is not running, page commands still work; OS commands will not.

---

## 3. Which file to put on the GitHub Release

The website download buttons expect **these exact filenames**:

| Asset | Who it is for | Put this on the release? |
|---|---|---|
| **`Iris-Orb-Setup.exe`** | Windows users who want one installer | **Yes — this is the main .exe** (same name the site uses) |
| **`Iris-Orb-Windows-v1.0.0.zip`** | Portable zip of the Orb package | Optional but the site links it |
| **`iris-browser-extension-v1.0.0.zip`** | Chrome “Load unpacked” | **Yes** — zip of the `iris-extension` folder |

**Do not upload** Python `python.exe`, `taskmgr.exe`, or random Electron `electron.exe`.

If you already built the installer on your PC, attach **that** file renamed to **`Iris-Orb-Setup.exe`**.  
If you have not built an installer yet, **do not invent a dummy .exe**. Ship the **extension zip + this guide**, and tell users to use **Local setup** until the setup.exe is built. A missing or fake installer will break the website “Download” button.

A packaged Orb (when you have it) is typically large (on the order of **100–160 MB**) because it can include Electron and/or the speech model. That size is expected.

---

## 4. Honest note on lag and “no API key”

- **No Iris API key is required** for: wake/listen (after the model is on disk), regex commands, local TTS, the Chrome extension’s page actions.
- **First listen** after boot can lag while Parakeet loads — wait until the orb says it is ready.
- **Polly / Bedrock / OpenRouter** need keys; they are upgrades, not a gate.
- **Chrome Web Speech** in the extension uses Google’s speech service inside Chrome (normal for Chromium). That is not an Iris OpenRouter key.

---

## 5. Quick checks

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Then:

1. `npm run orb`
2. Ask: “What is two plus two?” — you should **hear** the answer, no new tab.
3. Ask: “Search web for Iris voice assistant” — you should hear the search line, then Google opens.
4. Load the extension and try “scroll down” on any page.
