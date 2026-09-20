# How to Build & Run Iris — Developer & Judge Guide

This is the developer execution guide for **Iris**. Iris is an open-source, multimodal voice accessibility system for Windows powered by an interactive Floating Orb and AWS Cloud Intelligence.

---

## 1. Quickstart (Run Desktop Orb)

Iris provides full voice control over Windows (applications, volume, screen OCR, files, diagnostics, and spoken Q&A in English and Hindi).

### Prerequisites
- **OS:** Windows 10 or 11
- **Python:** 3.10+ (tested on Python 3.13)
- **Node.js:** 18+ (for Electron Orb GUI)
- **Microphone:** Standard built-in or USB microphone

### Setup Instructions

Open PowerShell in the cloned repository folder:

```powershell
# 1. Create and activate Python virtual environment
py -m venv .venv
.\.venv\Scripts\activate

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install Node.js dependencies
npm install
cd Orb
npm install
cd ..
```

*(Optional: If running Playwright browser automation tests)*
```powershell
playwright install chromium
```

---

## 2. Launching Iris

From the repository root:

```powershell
# Start Desktop Floating Orb (GUI)
npm run orb
```

Or CLI-only (terminal mode without the floating UI):
```powershell
npm run cli
```

### Interacting with the Floating Orb
- **Hands-Free Wake Word:** Speak *"Hey Iris"* or *"आईरिस"* to wake the assistant.
- **Push-to-Talk (Right-Click):** Hold right-click on the Orb while speaking; release to immediately transcribe and execute. A single right-click tap toggles listening mode.
- **Global Hotkey:** Press <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>Space</kbd> from any application to hide or reveal the Orb.
- **Multi-Turn Dialogue:** Iris remembers your conversation context for up to 120 seconds, allowing natural follow-up questions without repeating subject names.

---

## 3. Core Voice Commands

| Category | English Voice Command | Hindi Voice Command (हिन्दी) |
| :--- | :--- | :--- |
| **System Diagnostics** | *"Tell me how much RAM used"* | *"रैम कितनी इस्तेमाल हो रही है"* |
| **App Launching** | *"Open Notepad"* / *"Open Edge"* | *"नोटपैड खोलो"* / *"कैलकुलेटर खोलो"* |
| **Time & Date** | *"What time is it?"* | *"समय बताओ"* |
| **Web Navigation** | *"Open YouTube"* / *"Search for ISRO"* | *"यूट्यूब खोलो"* / *"गूगल पर सर्च करो"* |
| **Screen OCR** | *"What is on my screen?"* | *"मेरी स्क्रीन पर क्या है"* |
| **Accessibility** | *"Take a screenshot"* | *"स्क्रीनशॉट लो"* |
| **Volume Control** | *"Volume up"*, *"Mute audio"* | *"आवाज़ बढ़ाओ"*, *"म्यूट करो"* |
| **Conversational Q&A** | *"What is the capital of India?"* | *"भारत की राजधानी क्या है"* |

---

## 4. Environment & AWS Cloud Integration

Iris includes sensible defaults and local fallback engines. For full cloud capabilities, configure `.env` (refer to `.env.example`):

| Variable | Cloud Capability |
| :--- | :--- |
| `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` | Amazon Polly neural voice synthesis (Joanna / Aditi) |
| `AWS_DEFAULT_REGION` | AWS infrastructure region (e.g., `eu-north-1` or `ap-south-1`) |
| `DYNAMODB_TABLE_NAME` | Real-time zero-trust security audit table in DynamoDB |
| `OPENROUTER_API_KEYS` | LLM reasoning pool for complex open-ended actions |

---

## 5. Verification & Test Suite

Run the full automated test suite anytime:

```powershell
.\.venv\Scripts\pytest tests/ -q
```
