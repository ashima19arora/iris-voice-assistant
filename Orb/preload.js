const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("irisOrb", {
  // Window management & dragging
  startDrag: () => ipcRenderer.send("drag-start"),
  moveDrag: (delta) => ipcRenderer.send("drag-move", delta),
  endDrag: () => ipcRenderer.send("drag-end"),
  toggleExpand: () => ipcRenderer.send("toggle-expand"),
  collapse: () => ipcRenderer.send("collapse-window"),
  closeWindow: () => ipcRenderer.send("close-window"),
  minimizeWindow: () => ipcRenderer.send("minimize-window"),

  // State synchronization
  onStateChange: (callback) => {
    ipcRenderer.on("window-state", (_, state) => callback(state));
  },

  // Assistant communication
  sendCommand: (text, opts) => ipcRenderer.send("send-command", text, opts),
  startListening: (opts) => ipcRenderer.send("start-listening", opts),
  stopListening: () => ipcRenderer.send("stop-listening"),
  onUserTranscribed: (callback) => {
    ipcRenderer.on("user-transcribed", (_, text) => callback(text));
  },
  onAssistantMessage: (callback) => {
    ipcRenderer.on("assistant-message", (_, msg) => callback(msg));
  },
  onStatusUpdate: (callback) => {
    ipcRenderer.on("assistant-status", (_, status) => callback(status));
  },
  onStandaloneVoice: (callback) => {
    ipcRenderer.on("standalone-voice", (_, opts) => callback(opts));
  },
});
