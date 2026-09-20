/**
 * Iris Voice Assistant - Extension Background Service Worker
 */

chrome.runtime.onInstalled.addListener(() => {
  console.log('[Iris Extension] Installed and registered service worker.');
});

// Handle global command shortcut
chrome.commands.onCommand.addListener((command) => {
  if (command === 'toggle-iris-orb') {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]?.id) {
        chrome.tabs.sendMessage(tabs[0].id, { action: 'TOGGLE_FLOATING_ORB' });
      }
    });
  }
});
