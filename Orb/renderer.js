// Iris Orb Renderer Logic

const floatingOrb = document.getElementById("floatingOrb");
const chatHeader = document.getElementById("chatHeader");
const collapseBtn = document.getElementById("collapseBtn");
const closeBtn = document.getElementById("closeBtn");
const chatMessages = document.getElementById("chatMessages");
const userInput = document.getElementById("userInput");
const sendBtn = document.getElementById("sendBtn");
const micBtn = document.getElementById("micBtn");
const statusBadge = document.getElementById("statusBadge");
const statusText = document.getElementById("statusText");
const langToggleBtn = document.getElementById("langToggleBtn");
const langLabel = document.getElementById("langLabel");
const quickChips = document.getElementById("quickChips");

let currentLang = "en"; // "en" or "hi"

// Zero-friction pointer-based drag engine with hardware pointer capture
let isPointerDown = false;
let startPointerX = 0;
let startPointerY = 0;
let hasDragged = false;
let pointerDownTime = 0;
let currentDragTarget = null;
let isVoiceListening = false;
let dragRafId = null;

function setupDraggable(el) {
  if (!el) return;

  el.addEventListener("pointerdown", (e) => {
    // Only primary left button
    if (e.button !== 0) return;
    // Don't drag if user clicked interactive buttons inside header
    if (e.target.closest("button") || e.target.closest("input")) return;

    isPointerDown = true;
    hasDragged = false;
    pointerDownTime = Date.now();
    currentDragTarget = el;
    startPointerX = e.clientX;
    startPointerY = e.clientY;

    try {
      el.setPointerCapture(e.pointerId);
    } catch (err) {}

    if (window.irisOrb) {
      window.irisOrb.startDrag();
    }
  });

  el.addEventListener("pointermove", (e) => {
    if (!isPointerDown) return;

    const dx = e.clientX - startPointerX;
    const dy = e.clientY - startPointerY;

    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
      hasDragged = true;
    }

    if (hasDragged && window.irisOrb) {
      if (!dragRafId) {
        dragRafId = requestAnimationFrame(() => {
          dragRafId = null;
          if (window.irisOrb && isPointerDown) {
            window.irisOrb.moveDrag();
          }
        });
      }
    }
  });

  const handlePointerEnd = (e) => {
    if (!isPointerDown) return;
    isPointerDown = false;

    if (dragRafId) {
      cancelAnimationFrame(dragRafId);
      dragRafId = null;
    }

    try {
      el.releasePointerCapture(e.pointerId);
    } catch (err) {}

    if (window.irisOrb) {
      window.irisOrb.endDrag();
    }

    const clickDuration = Date.now() - pointerDownTime;

    // Only toggle expand/collapse on a genuine, fast click (< 250ms with no drag movement)
    // If user clicked and held (> 250ms), it is treated as a hold gesture and NEVER expands!
    if (!hasDragged && clickDuration < 250 && currentDragTarget === floatingOrb) {
      if (window.irisOrb) {
        window.irisOrb.toggleExpand();
      }
    }

    currentDragTarget = null;
    hasDragged = false;
  };

  el.addEventListener("pointerup", handlePointerEnd);
  el.addEventListener("pointercancel", handlePointerEnd);
}

setupDraggable(floatingOrb);
setupDraggable(chatHeader);

// Prevent browser context menu across the entire Orb window
window.addEventListener("contextmenu", (e) => e.preventDefault());

// ============================================================
// PUSH-TO-TALK VIA RIGHT-CLICK & HOLD (COLLAPSED & EXPANDED)
// ============================================================
let isRightClickListening = false;

function setupRightClickVoice(el) {
  if (!el) return;

  el.addEventListener("mousedown", (e) => {
    if (e.button === 2) { // Right click
      e.preventDefault();
      e.stopPropagation();
      if (!isRightClickListening) {
        isRightClickListening = true;
        updateStatus("listening", "LISTENING...");
        if (window.irisOrb) {
          window.irisOrb.startListening({ lang: currentLang });
        }
      }
    }
  });

  const handleRightClickUp = (e) => {
    if (e.button === 2 && isRightClickListening) {
      e.preventDefault();
      e.stopPropagation();
      isRightClickListening = false;
      updateStatus("thinking", "TRANSCRIBING...");
      if (window.irisOrb) {
        window.irisOrb.stopListening();
      }
    }
  };

  window.addEventListener("mouseup", handleRightClickUp);
}

setupRightClickVoice(floatingOrb);
setupRightClickVoice(chatHeader);

// Header collapse and close buttons
if (collapseBtn) {
  collapseBtn.addEventListener("click", () => {
    if (window.irisOrb) {
      window.irisOrb.collapse();
    }
  });
}

if (closeBtn) {
  closeBtn.addEventListener("click", () => {
    if (window.irisOrb) {
      window.irisOrb.closeWindow();
    }
  });
}

// Window state changes from main process
if (window.irisOrb) {
  window.irisOrb.onStateChange(({ expanded }) => {
    if (expanded) {
      document.body.classList.remove("collapsed");
      document.body.classList.add("expanded");
      setTimeout(() => {
        if (userInput) userInput.focus();
      }, 150);
    } else {
      document.body.classList.remove("expanded");
      document.body.classList.add("collapsed");
    }
  });

  // Assistant status updates (ready, listening, thinking, speaking)
  window.irisOrb.onStatusUpdate((status) => {
    updateStatus(status.state || "ready", status.text);
  });

  // Real voice transcript from microphone
  window.irisOrb.onUserTranscribed((text) => {
    if (text) {
      appendMessage("user", text);
    }
  });

  // Real assistant response messages from Python backend
  window.irisOrb.onAssistantMessage((msg) => {
    const text = msg.text || msg.content || msg.message || "Done.";
    appendMessage("assistant", text);
    updateStatus("ready", "READY");
  });
}

function updateStatus(state, label) {
  const s = (state || "ready").toLowerCase();
  
  if (floatingOrb) {
    floatingOrb.className = "orb-wrapper";
    if (["listening", "thinking", "speaking", "sleeping"].includes(s)) {
      floatingOrb.classList.add(s);
    }
  }

  if (micBtn) {
    if (s === "listening") {
      micBtn.classList.add("listening");
      isVoiceListening = true;
    } else {
      micBtn.classList.remove("listening");
      isVoiceListening = false;
    }
  }

  if (statusBadge) {
    statusBadge.className = "status-badge";
    if (["listening", "thinking", "speaking", "sleeping"].includes(s)) {
      statusBadge.classList.add(s);
    }
  }

  if (statusText) {
    if (s === "sleeping") {
      statusText.textContent = "STANDBY";
    } else {
      statusText.textContent = (label || s).toUpperCase();
    }
  }
}

// Chat Messaging
function appendMessage(role, text) {
  if (!chatMessages || !text) return;

  const msgEl = document.createElement("div");
  msgEl.className = `message ${role}`;

  const now = new Date();
  const timeStr = now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  msgEl.innerHTML = `
    <div class="bubble">${escapeHtml(text)}</div>
    <span class="time-stamp">${timeStr}</span>
  `;

  chatMessages.appendChild(msgEl);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// Handle sending typed commands
function handleSend() {
  if (!userInput) return;
  const text = userInput.value.trim();
  if (!text) return;

  appendMessage("user", text);
  userInput.value = "";

  updateStatus("thinking", "PROCESSING");

  // Send real command to Python backend through IPC with active language
  if (window.irisOrb) {
    window.irisOrb.sendCommand(text, { lang: currentLang });
  }
}

if (sendBtn) {
  sendBtn.addEventListener("click", handleSend);
}

if (userInput) {
  userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      handleSend();
    }
  });
}

// Microphone voice button
if (micBtn) {
  micBtn.addEventListener("click", () => {
    if (window.irisOrb) {
      updateStatus("listening", "LISTENING...");
      window.irisOrb.startListening({ lang: currentLang });
    }
  });
}

// Quick action chips & multilingual catalogs
const HINDI_CHIPS = [
  { label: "समय बताओ", cmd: "समय बताओ" },
  { label: "नोटपैड खोलो", cmd: "नोटपैड खोलो" },
  { label: "स्क्रीनशॉट लो", cmd: "स्क्रीनशॉट लो" },
  { label: "यूट्यूब चलाओ", cmd: "यूट्यूब खोलो" }
];

const ENGLISH_CHIPS = [
  { label: "What's on screen?", cmd: "What is on my screen?" },
  { label: "Open apps", cmd: "What apps are running?" },
  { label: "Open Notepad", cmd: "Open Notepad" },
  { label: "Volume up", cmd: "Volume up" }
];

function renderChips(items) {
  if (!quickChips) return;
  quickChips.innerHTML = "";
  items.forEach((item) => {
    const btn = document.createElement("button");
    btn.className = "chip";
    btn.setAttribute("data-cmd", item.cmd);
    btn.textContent = item.label;
    btn.addEventListener("click", () => {
      if (userInput) userInput.value = item.cmd;
      handleSend();
    });
    quickChips.appendChild(btn);
  });
}

function setLanguage(lang) {
  currentLang = lang;
  if (lang === "hi") {
    if (langLabel) langLabel.textContent = "🇮🇳 हिन्दी";
    if (langToggleBtn) {
      langToggleBtn.classList.add("active-hi");
      langToggleBtn.title = "वॉइस भाषा: हिन्दी (अमेज़न पॉली अदिति) - क्लिक करके English बदलें";
    }
    if (userInput) userInput.placeholder = "आईरिस से पूछें (उदा. नोटपैड खोलो, समय बताओ)...";
    renderChips(HINDI_CHIPS);
    appendMessage("assistant", "भाषा मोड: 🇮🇳 हिन्दी। वॉइस इंजन: Amazon Polly (Aditi)। आप बोलकर या लिखकर कमांड दे सकते हैं।");
  } else {
    if (langLabel) langLabel.textContent = "🌐 EN";
    if (langToggleBtn) {
      langToggleBtn.classList.remove("active-hi");
      langToggleBtn.title = "Voice language: English (Amazon Polly Joanna) - Click to switch to हिन्दी";
    }
    if (userInput) userInput.placeholder = "Ask Iris or type a command...";
    renderChips(ENGLISH_CHIPS);
    appendMessage("assistant", "Voice mode: 🌐 English (Amazon Polly Joanna).");
  }
}

if (langToggleBtn) {
  langToggleBtn.addEventListener("click", () => {
    setLanguage(currentLang === "en" ? "hi" : "en");
  });
}

// Initial chip binding
renderChips(ENGLISH_CHIPS);
