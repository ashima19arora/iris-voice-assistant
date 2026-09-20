/**
 * Iris Voice Assistant - In-Page Floating Orb & Content Automation Script
 */

let floatingOrb = null;
let inpageRecognition = null;
let isListeningOnPage = false;

// Pre-load voices for SpeechSynthesis
if ('speechSynthesis' in window) {
  window.speechSynthesis.getVoices();
  window.speechSynthesis.onvoiceschanged = () => {
    window.speechSynthesis.getVoices();
  };
}

function toggleFloatingOrb() {
  if (!floatingOrb) {
    createFloatingOrb();
    return;
  }
  if (floatingOrb.style.display === 'none') {
    floatingOrb.style.display = 'flex';
  } else {
    floatingOrb.style.display = 'none';
  }
}

function createFloatingOrb() {
  if (floatingOrb) {
    toggleFloatingOrb();
    return;
  }

  floatingOrb = document.createElement('div');
  floatingOrb.id = 'iris-inpage-orb';
  floatingOrb.innerHTML = `
    <div class="iris-orb-float-glow" id="irisFloatGlow"></div>
    <div class="iris-orb-float-core">
      <svg viewBox="0 0 24 24" width="20" height="20" fill="white">
        <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm5-3c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
      </svg>
    </div>
    <div class="iris-float-tooltip" id="irisFloatTooltip">Click to Speak / Read</div>
  `;

  document.body.appendChild(floatingOrb);

  // Dragging logic
  let isDragging = false;
  let startX, startY, startLeft, startTop;

  floatingOrb.addEventListener('mousedown', (e) => {
    isDragging = true;
    startX = e.clientX;
    startY = e.clientY;
    const rect = floatingOrb.getBoundingClientRect();
    startLeft = rect.left;
    startTop = rect.top;
    floatingOrb.style.transition = 'none';
  });

  window.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    const dx = e.clientX - startX;
    const dy = e.clientY - startY;
    floatingOrb.style.left = `${Math.max(10, Math.min(window.innerWidth - 60, startLeft + dx))}px`;
    floatingOrb.style.top = `${Math.max(10, Math.min(window.innerHeight - 60, startTop + dy))}px`;
    floatingOrb.style.right = 'auto';
    floatingOrb.style.bottom = 'auto';
  });

  window.addEventListener('mouseup', () => {
    if (isDragging) {
      isDragging = false;
      floatingOrb.style.transition = 'all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275)';
    }
  });

  floatingOrb.addEventListener('click', (e) => {
    if (Math.abs(e.clientX - startX) > 5 || Math.abs(e.clientY - startY) > 5) return;
    handleOrbClick();
  });
}

function updateTooltip(text) {
  const tip = document.getElementById('irisFloatTooltip');
  if (tip) {
    tip.textContent = text;
    tip.style.opacity = '1';
    setTimeout(() => { tip.style.opacity = ''; }, 3000);
  }
}

function handleOrbClick() {
  const selection = window.getSelection().toString().trim();
  if (selection) {
    speakText(selection);
    return;
  }

  // If already speaking, stop
  if (window.speechSynthesis.speaking) {
    window.speechSynthesis.cancel();
    updateTooltip('Speech stopped');
    return;
  }

  // Toggle in-page speech recognition
  if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    if (isListeningOnPage) {
      stopInPageListening();
    } else {
      startInPageListening();
    }
  } else {
    speakSummary();
  }
}

function startInPageListening() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  try {
    inpageRecognition = new SpeechRecognition();
    inpageRecognition.continuous = false;
    inpageRecognition.interimResults = false;
    inpageRecognition.lang = 'en-US';

    inpageRecognition.onstart = () => {
      isListeningOnPage = true;
      floatingOrb.classList.add('iris-listening');
      updateTooltip('Listening... Speak now');
    };

    inpageRecognition.onresult = (event) => {
      const command = event.results[0][0].transcript.trim();
      updateTooltip(`"${command}"`);
      dispatchOnPageCommand(command);
    };

    inpageRecognition.onerror = (e) => {
      console.warn('[Iris In-Page] Speech error:', e.error);
      stopInPageListening();
      if (e.error === 'not-allowed') {
        updateTooltip('Microphone access blocked');
      } else {
        speakSummary();
      }
    };

    inpageRecognition.onend = () => {
      stopInPageListening();
    };

    inpageRecognition.start();
  } catch (err) {
    console.warn('[Iris In-Page] Could not start speech recognition:', err);
    speakSummary();
  }
}

function stopInPageListening() {
  isListeningOnPage = false;
  if (floatingOrb) floatingOrb.classList.remove('iris-listening');
  if (inpageRecognition) {
    try { inpageRecognition.stop(); } catch (e) {}
    inpageRecognition = null;
  }
}

function dispatchOnPageCommand(cmd) {
  const lower = cmd.toLowerCase();

  if (lower.includes('scroll down') || lower.includes('page down')) {
    window.scrollBy({ top: window.innerHeight * 0.75, behavior: 'smooth' });
    updateTooltip('Scrolled down');
  } else if (lower.includes('scroll up') || lower.includes('page up')) {
    window.scrollBy({ top: -window.innerHeight * 0.75, behavior: 'smooth' });
    updateTooltip('Scrolled up');
  } else if (lower.includes('scroll to top') || lower.includes('go to top')) {
    window.scrollTo({ top: 0, behavior: 'smooth' });
    updateTooltip('Top of page');
  } else if (lower.includes('scroll to bottom') || lower.includes('go to bottom')) {
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    updateTooltip('Bottom of page');
  } else if (lower.includes('read page') || lower.includes('read')) {
    speakSummary();
  } else if (lower.includes('highlight') || lower.includes('links')) {
    highlightInteractiveElements();
    updateTooltip('Links highlighted');
  } else {
    // Try forwarding to local Desktop Orb bridge if active
    fetch('http://127.0.0.1:7878/message', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: cmd })
    }).then(res => {
      if (res.ok) {
        updateTooltip(`Dispatched: "${cmd}"`);
      }
    }).catch(() => {
      updateTooltip(`Dispatched: "${cmd}"`);
    });
  }
}

// Speak aloud webpage summary or selected text
function speakSummary() {
  if (window.speechSynthesis.speaking) {
    window.speechSynthesis.cancel();
    return;
  }

  const selection = window.getSelection().toString().trim();
  let textToRead = selection;

  if (!textToRead) {
    const mainHeading = document.querySelector('h1, h2')?.innerText || document.title;
    textToRead = `You are on ${document.title}. Main heading: ${mainHeading}.`;
  }

  speakText(textToRead);
}

function speakText(text) {
  if (!('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel();

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1.0;
  utterance.pitch = 1.0;

  const voices = window.speechSynthesis.getVoices();
  if (voices.length > 0) {
    const enVoice = voices.find(v => v.lang.startsWith('en')) || voices[0];
    utterance.voice = enVoice;
  }

  window.speechSynthesis.speak(utterance);
  updateTooltip('Speaking text...');
}

// Handle messages from Extension Popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'TOGGLE_FLOATING_ORB') {
    toggleFloatingOrb();
    sendResponse({ status: 'ok' });
    return true;
  }

  if (request.action === 'EXECUTE_COMMAND') {
    const cmd = request.command || '';
    dispatchOnPageCommand(cmd);
    sendResponse({ status: `Executed: ${cmd}` });
    return true;
  }
});

// Highlight interactive elements on page for accessibility navigation
function highlightInteractiveElements() {
  const elements = document.querySelectorAll('a, button, input, [role="button"]');
  elements.forEach((el, index) => {
    el.style.outline = '2px solid #38bdf8';
    el.style.outlineOffset = '2px';
    el.setAttribute('data-iris-id', index + 1);
  });

  setTimeout(() => {
    elements.forEach(el => {
      el.style.outline = '';
      el.style.outlineOffset = '';
    });
  }, 4000);
}

// Listen for keyboard shortcut (Ctrl+Shift+Space) to toggle Iris Orb
window.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.code === 'Space' || e.keyCode === 32 || e.key === ' ')) {
    e.preventDefault();
    toggleFloatingOrb();
  } else if (e.altKey && e.shiftKey && e.code === 'KeyI') {
    e.preventDefault();
    toggleFloatingOrb();
  }
});
