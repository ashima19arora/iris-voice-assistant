# Iris Floating Desktop Orb & Overlay

A lightweight, persistent, frameless, and transparent desktop assistant overlay for Iris.

## Features
- **Always-on-Top Floating Orb:** Stays visible over all applications, web browsers, and full-screen windows.
- **Strict Screen Clamping:** Freely draggable anywhere across the screen, automatically clamped to display boundaries so it cannot leave the screen or hide behind the taskbar.
- **Dynamic Resize Architecture:**
  - **Collapsed State (84x84 px):** Unobtrusive circular glowing orb leaving 99.9% of the screen clickable for normal work.
  - **Expanded State (380x560 px):** Ultra-sleek dark glassmorphic chatbox with the orb anchored beside the typing dock.
- **Smart Edge Adjustment:** Expands inward from whichever screen corner it sits on, ensuring zero content clipping.
- **Real-Time Visual Feedback:** Glowing aura with distinct states for `READY`, `LISTENING` (emerald), `THINKING` (purple), and `SPEAKING` (cyan).
- **Embedded Local Bridge:** Listens on `http://127.0.0.1:7878` for real-time status and transcript updates from `assistant.py`.

## Quick Start

From within the `Orb` directory:
```powershell
npm start
```

Or from the project root:
```powershell
npm run orb
```
