/**
 * Iris Voice Assistant - Extension Popup Logic
 */

let isListening = false;
let recognition = null;

const mainOrb = document.getElementById('mainOrb');
const statusBadge = document.getElementById('statusBadge');
const orbInstruction = document.getElementById('orbInstruction');
const transcriptText = document.getElementById('transcriptText');
const toggleFloatingOrbBtn = document.getElementById('toggleFloatingOrbBtn');
const permBanner = document.getElementById('permBanner');
const grantPermBtn = document.getElementById('grantPermBtn');
const commandForm = document.getElementById('commandForm');
const commandInput = document.getElementById('commandInput');

// Pre-warm Speech Synthesis voices so voice doesn't stall on first use
if ('speechSynthesis' in window) {
  window.speechSynthesis.getVoices();
  window.speechSynthesis.onvoiceschanged = () => {
    window.speechSynthesis.getVoices();
  };
}

function openPermissionTab() {
  chrome.tabs.create({ url: chrome.runtime.getURL('permission.html') });
}

if (grantPermBtn) {
  grantPermBtn.addEventListener('click', openPermissionTab);
}

// Initialize Web Speech Recognition if available
if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = 'en-US';

  recognition.onstart = () => {
    isListening = true;
    if (permBanner) permBanner.style.display = 'none';
    statusBadge.textContent = 'LISTENING';
    statusBadge.classList.add('listening');
    orbInstruction.textContent = 'Speak command now...';
    mainOrb.style.transform = 'scale(1.1)';
  };

  recognition.onresult = (event) => {
    let interim = '';
    let final = '';
    for (let i = event.resultIndex; i < event.results.length; ++i) {
      if (event.results[i].isFinal) {
        final += event.results[i][0].transcript;
      } else {
        interim += event.results[i][0].transcript;
      }
    }
    const current = final || interim;
    transcriptText.textContent = `"${current}"`;

    if (final) {
      executeCommand(final.trim());
    }
  };

  recognition.onerror = (event) => {
    console.warn('[Iris Extension] Speech recognition error:', event.error);
    isListening = false;
    mainOrb.style.transform = 'scale(1)';
    statusBadge.classList.remove('listening');

    if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
      statusBadge.textContent = 'MIC BLOCKED';
      if (permBanner) permBanner.style.display = 'flex';
      orbInstruction.textContent = 'Click "Allow Mic" above to enable voice.';
    } else {
      statusBadge.textContent = 'ERROR';
      orbInstruction.textContent = 'Click Orb to retry or type below.';
    }
  };

  recognition.onend = () => {
    isListening = false;
    statusBadge.classList.remove('listening');
    if (statusBadge.textContent === 'LISTENING') {
      statusBadge.textContent = 'READY';
      orbInstruction.textContent = 'Click Orb to Listen';
    }
    mainOrb.style.transform = 'scale(1)';
  };
} else {
  statusBadge.textContent = 'TYPING ONLY';
  orbInstruction.textContent = 'Web speech not supported in this browser.';
}

mainOrb.addEventListener('click', () => {
  if (!recognition) {
    transcriptText.textContent = 'Speech recognition not available. Please type your command below.';
    return;
  }
  if (!isListening) {
    try {
      recognition.start();
    } catch (e) {
      console.warn('Recognition start exception, retrying:', e);
      try {
        recognition.stop();
        setTimeout(() => recognition.start(), 100);
      } catch (err) {
        openPermissionTab();
      }
    }
  } else {
    recognition.stop();
  }
});

// Quick action chips
document.querySelectorAll('.chip').forEach(btn => {
  btn.addEventListener('click', () => {
    const cmd = btn.getAttribute('data-cmd');
    transcriptText.textContent = `"${cmd}"`;
    executeCommand(cmd);
  });
});

// Command text input form
if (commandForm) {
  commandForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const cmd = (commandInput.value || '').trim();
    if (cmd) {
      transcriptText.textContent = `"${cmd}"`;
      executeCommand(cmd);
      commandInput.value = '';
    }
  });
}

// Dispatch command to active tab content script
function executeCommand(command) {
  statusBadge.textContent = 'EXECUTING';
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]?.id) {
      chrome.tabs.sendMessage(tabs[0].id, { action: 'EXECUTE_COMMAND', command: command }, (response) => {
        if (chrome.runtime.lastError) {
          transcriptText.textContent = `Command: ${command}`;
        } else if (response && response.status) {
          transcriptText.textContent = `${response.status}`;
        }
        setTimeout(() => {
          statusBadge.textContent = 'READY';
          orbInstruction.textContent = 'Click Orb to Listen';
        }, 1800);
      });
    }
  });
}

// Toggle on-page floating orb
toggleFloatingOrbBtn.addEventListener('click', (e) => {
  e.preventDefault();
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (tabs[0]?.id) {
      chrome.tabs.sendMessage(tabs[0].id, { action: 'TOGGLE_FLOATING_ORB' });
    }
  });
});
