# iris-voice-assistant
Digital braille for the internet — a voice assistant that does what you say.

## Run

```powershell
npm run dev
```

This starts `assistant.py` with the project virtualenv. Say commands after you hear that Iris is active.

## Voice commands (examples)

- **RAM:** "tell me how much RAM used"
- **Settings:** "open settings"
- **File:** "create a .txt file on desktop"
- **Website:** "open gov.in"
- Also: open YouTube/WhatsApp, volume, screenshot, scroll, zoom, lock screen, "what is photosynthesis"

## How intent matching works

`actions/intent_parser.py` is rule-based (regex), fully offline. It strips polite filler ("please", "can you"), then matches the **last real command** in a noisy sentence.

## Add a new voice command (under 5 lines)

1. Add a regex in `actions/intent_parser.py` that returns `Intent(name="MY_INTENT", params={...})`.
2. Add a handler in `actions/registry.py` `INTENT_HANDLERS`.
3. If needed, add the intent name to `actions/security/policy.py` `INTENT_TIERS`.
4. Put new site names or apps in `actions/config.py`.

## Safety

Writes only go to Desktop, Documents, or `~/Iris`. URLs must be `http`/`https`. Apps are allowlisted. No `eval`/`exec`/unsanitized `shell=True`.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```
