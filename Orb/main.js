const { app, BrowserWindow, ipcMain, screen, globalShortcut } = require("electron");
const path = require("path");
const http = require("http");
const { spawn, exec } = require("child_process");
const fs = require("fs");

// Isolate userData in dev mode using process PID to guarantee zero lock collisions
let devUserData = null;
if (!app.isPackaged) {
  devUserData = path.join(app.getPath("temp"), `iris-orb-dev-${process.pid}`);
  try {
    if (!fs.existsSync(devUserData)) {
      fs.mkdirSync(devUserData, { recursive: true });
    }
    app.setPath("userData", devUserData);
  } catch (e) {}
}

// In production, ensure only a single instance of Iris Orb runs at a time
if (app.isPackaged) {
  const gotTheLock = app.requestSingleInstanceLock();
  if (!gotTheLock) {
    app.quit();
    process.exit(0);
  }
}

// Disable GPU shader disk cache and HTTP cache to avoid Access Denied (0x5) cache lock collisions
app.commandLine.appendSwitch("disable-gpu-shader-disk-cache");
app.commandLine.appendSwitch("disable-http-cache");

// Configuration dimensions: Floating Orb on LEFT (96px) + Chatbox on RIGHT (340px)
const COLLAPSED_SIZE = 96;
const EXPANDED_WIDTH = 450;
const EXPANDED_HEIGHT = 380;

let mainWindow = null;
let isExpanded = false;
let cachedDragState = null;
let pythonBridge = null;

// Dynamic discovery of Python bridge script and interpreter across dev and packaged runtimes
function findBridgeScript() {
  const candidates = [
    path.join(__dirname, "scripts", "orb_bridge.py"),
    path.join(__dirname, "..", "scripts", "orb_bridge.py"),
    path.join(__dirname, "..", "..", "scripts", "orb_bridge.py"),
    process.resourcesPath ? path.join(process.resourcesPath, "scripts", "orb_bridge.py") : null,
    process.resourcesPath ? path.join(process.resourcesPath, "app", "scripts", "orb_bridge.py") : null,
    path.join(process.cwd(), "scripts", "orb_bridge.py"),
  ];
  for (const c of candidates) {
    if (c && fs.existsSync(c)) return c;
  }
  return null;
}

function findPythonExecutable(bridgeScript) {
  const candidates = [];
  if (bridgeScript) {
    const parent = path.resolve(path.dirname(bridgeScript), "..");
    candidates.push(path.join(parent, ".venv", "Scripts", "python.exe"));
    candidates.push(path.join(parent, ".venv", "bin", "python"));
  }
  candidates.push(path.join(path.resolve(__dirname, ".."), ".venv", "Scripts", "python.exe"));
  candidates.push(path.join(path.resolve(__dirname, "..", ".."), ".venv", "Scripts", "python.exe"));
  if (process.env.LOCALAPPDATA) {
    candidates.push(path.join(process.env.LOCALAPPDATA, "Programs", "Python", "Python311", "python.exe"));
    candidates.push(path.join(process.env.LOCALAPPDATA, "Programs", "Python", "Python310", "python.exe"));
    candidates.push(path.join(process.env.LOCALAPPDATA, "Programs", "Python", "Python312", "python.exe"));
  }
  for (const p of candidates) {
    if (p && fs.existsSync(p)) return p;
  }
  return "python";
}

function createWindow() {
  const primaryDisplay = screen.getPrimaryDisplay();
  const { workArea } = primaryDisplay;

  // Default position: lower-right area of screen
  const initialX = workArea.x + workArea.width - COLLAPSED_SIZE - 40;
  const initialY = workArea.y + workArea.height - COLLAPSED_SIZE - 60;

  mainWindow = new BrowserWindow({
    width: COLLAPSED_SIZE,
    height: COLLAPSED_SIZE,
    minWidth: COLLAPSED_SIZE,
    minHeight: COLLAPSED_SIZE,
    maxWidth: COLLAPSED_SIZE,
    maxHeight: COLLAPSED_SIZE,
    x: initialX,
    y: initialY,
    frame: false,
    transparent: true,
    backgroundColor: "#00000000",
    alwaysOnTop: true,
    resizable: false,
    maximizable: false,
    fullscreenable: false,
    hasShadow: false,
    skipTaskbar: true,
    icon: path.join(__dirname, "assets", "iris-image.png"),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.on("maximize", () => {
    mainWindow.unmaximize();
  });

  mainWindow.setAlwaysOnTop(true, "screen-saver");
  mainWindow.setVisibleOnAllWorkspaces(true);

  mainWindow.loadFile(path.join(__dirname, "index.html"));

  // Register global hotkey: Ctrl + Shift + Space to toggle hide/show anywhere in Windows
  try {
    globalShortcut.register("CommandOrControl+Shift+Space", () => {
      if (mainWindow) {
        if (mainWindow.isVisible()) {
          mainWindow.hide();
        } else {
          mainWindow.show();
          mainWindow.focus();
        }
      }
    });
  } catch (e) {
    console.error("Failed to register global shortcut:", e);
  }

  // Start internal local HTTP bridge silently
  startAssistantBridge();

  // Start persistent Python bridge process
  startPythonBridge();
}

app.on("second-instance", () => {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    if (!mainWindow.isVisible()) mainWindow.show();
    mainWindow.focus();
  }
});

// ------------------------------------------------------------
// ULTRA-FAST, ZERO-FRICTION DRAG ENGINE (DIP NATIVE TRACKING)
// ------------------------------------------------------------
ipcMain.on("drag-start", () => {
  if (!mainWindow) return;
  const cursor = screen.getCursorScreenPoint();
  const [winX, winY] = mainWindow.getPosition();
  const [winW, winH] = mainWindow.getSize();
  const display = screen.getDisplayNearestPoint(cursor);

  // Exact cursor offset relative to window top-left in DIPs
  cachedDragState = {
    offsetX: cursor.x - winX,
    offsetY: cursor.y - winY,
    winW,
    winH,
    workArea: display.workArea,
  };
});

ipcMain.on("drag-move", () => {
  if (!mainWindow || !cachedDragState) return;
  const cursor = screen.getCursorScreenPoint();
  const { offsetX, offsetY, winW, winH, workArea } = cachedDragState;

  let newX = cursor.x - offsetX;
  let newY = cursor.y - offsetY;

  // Clamping with 4px buffer so dragging near edges never causes Windows Aero Snap
  const minX = workArea.x + 4;
  const maxX = workArea.x + workArea.width - winW - 4;
  const minY = workArea.y + 8;
  const maxY = workArea.y + workArea.height - winH - 4;

  newX = Math.max(minX, Math.min(newX, maxX));
  newY = Math.max(minY, Math.min(newY, maxY));

  mainWindow.setPosition(Math.round(newX), Math.round(newY));
});

ipcMain.on("drag-end", () => {
  cachedDragState = null;
});

// ------------------------------------------------------------
// EXPAND & COLLAPSE LOGIC (ORB ON THE LEFT, CHATBOX ON RIGHT)
// ------------------------------------------------------------
ipcMain.on("toggle-expand", () => {
  if (!mainWindow) return;
  if (isExpanded) {
    collapseWindow();
  } else {
    expandWindow();
  }
});

ipcMain.on("collapse-window", () => {
  collapseWindow();
});

ipcMain.on("minimize-window", () => {
  collapseWindow();
});

ipcMain.on("close-window", () => {
  if (pythonBridge) {
    try {
      pythonBridge.kill();
    } catch (e) {}
  }
  if (mainWindow) {
    mainWindow.close();
  }
});

function expandWindow(fromBridge = false) {
  if (!mainWindow || isExpanded) return;

  const currentDisplay = screen.getDisplayNearestPoint(screen.getCursorScreenPoint());
  const { workArea } = currentDisplay;
  const [curX, curY] = mainWindow.getPosition();

  // The floating Orb stays on the LEFT; chatbox opens to the RIGHT
  let targetX = curX;
  let targetY = curY - Math.round((EXPANDED_HEIGHT - COLLAPSED_SIZE) / 2);

  // Boundary clamping: if opening to the right hits right edge, slide left
  if (targetX + EXPANDED_WIDTH > workArea.x + workArea.width - 10) {
    targetX = workArea.x + workArea.width - EXPANDED_WIDTH - 10;
  }
  const minX = workArea.x + 10;
  const minY = workArea.y + 10;
  const maxY = workArea.y + workArea.height - EXPANDED_HEIGHT - 10;

  targetX = Math.max(minX, targetX);
  targetY = Math.max(minY, Math.min(targetY, maxY));

  // Lock exact bounds
  mainWindow.setMinimumSize(EXPANDED_WIDTH, EXPANDED_HEIGHT);
  mainWindow.setMaximumSize(EXPANDED_WIDTH, EXPANDED_HEIGHT);

  mainWindow.setBounds({
    x: Math.round(targetX),
    y: Math.round(targetY),
    width: EXPANDED_WIDTH,
    height: EXPANDED_HEIGHT,
  });

  isExpanded = true;
  mainWindow.webContents.send("window-state", { expanded: true });

  if (!fromBridge) {
    sendBridgeCommand({ type: "user_active" });
  }
}

function collapseWindow(fromBridge = false) {
  if (!mainWindow || !isExpanded) return;

  const currentDisplay = screen.getDisplayNearestPoint(screen.getCursorScreenPoint());
  const { workArea } = currentDisplay;
  const [curX, curY] = mainWindow.getPosition();

  // Floating Orb was anchored on the LEFT of the expanded box
  let orbX = curX;
  let orbY = curY + Math.round((EXPANDED_HEIGHT - COLLAPSED_SIZE) / 2);

  const minX = workArea.x + 8;
  const maxX = workArea.x + workArea.width - COLLAPSED_SIZE - 8;
  const minY = workArea.y + 8;
  const maxY = workArea.y + workArea.height - COLLAPSED_SIZE - 8;

  orbX = Math.max(minX, Math.min(orbX, maxX));
  orbY = Math.max(minY, Math.min(orbY, maxY));

  // Lock exact bounds
  mainWindow.setMinimumSize(COLLAPSED_SIZE, COLLAPSED_SIZE);
  mainWindow.setMaximumSize(COLLAPSED_SIZE, COLLAPSED_SIZE);

  mainWindow.setBounds({
    x: Math.round(orbX),
    y: Math.round(orbY),
    width: COLLAPSED_SIZE,
    height: COLLAPSED_SIZE,
  });

  isExpanded = false;
  mainWindow.webContents.send("window-state", { expanded: false });

  if (!fromBridge) {
    sendBridgeCommand({ type: "sleep" });
  }
}

// ------------------------------------------------------------
// PYTHON BRIDGE PROCESS MANAGEMENT
// ------------------------------------------------------------
function startPythonBridge() {
  const bridgeScript = findBridgeScript();
  if (!bridgeScript) {
    console.log("[Iris Orb] Python bridge script not found. Activating Standalone Mode.");
    return;
  }

  const pyExe = findPythonExecutable(bridgeScript);
  const bridgeCwd = path.resolve(path.dirname(bridgeScript), "..");
  console.log(`[Iris Orb] Spawning Python bridge with: ${pyExe} in ${bridgeCwd}`);

  try {
    pythonBridge = spawn(pyExe, ["-u", bridgeScript], {
      cwd: bridgeCwd,
      stdio: ["pipe", "pipe", "pipe"],
      env: {
        ...process.env,
        PYTHONUNBUFFERED: "1",
        PYGAME_HIDE_SUPPORT_PROMPT: "1",
      },
      windowsHide: true,
    });

    let buffer = "";
    pythonBridge.stdout.on("data", (chunk) => {
      buffer += chunk.toString("utf8");
      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed) continue;
        try {
          const data = JSON.parse(trimmed);
          handleBridgeMessage(data);
        } catch (e) {
          console.log("[Python Bridge Raw]", trimmed);
        }
      }
    });

    pythonBridge.stderr.on("data", (data) => {
      console.log("[Python Bridge Log]", data.toString("utf8").trim());
    });

    pythonBridge.on("exit", (code) => {
      console.log(`[Python Bridge] Process exited with code ${code}`);
      pythonBridge = null;
    });

    pythonBridge.on("error", (err) => {
      console.error("[Python Bridge Error]", err.message);
      pythonBridge = null;
    });
  } catch (err) {
    console.error("[Python Bridge Spawn Exception]", err);
  }
}

function handleBridgeMessage(data) {
  if (!mainWindow || mainWindow.isDestroyed()) return;

  if (data.type === "status") {
    mainWindow.webContents.send("assistant-status", data);
  } else if (data.type === "transcribed") {
    mainWindow.webContents.send("user-transcribed", data.text);
  } else if (data.type === "result") {
    mainWindow.webContents.send("assistant-message", {
      success: data.success,
      intent: data.intent,
      text: data.message || data.text,
    });
  } else if (data.type === "wake") {
    if (!isExpanded) {
      expandWindow(true);
    }
  } else if (data.type === "collapse") {
    if (isExpanded) {
      collapseWindow(true);
    }
  } else if (data.type === "ready") {
    mainWindow.webContents.send("assistant-status", {
      state: "ready",
      text: "READY",
    });
  }
}

function sendBridgeCommand(cmdObj) {
  if (pythonBridge && pythonBridge.stdin && !pythonBridge.killed) {
    try {
      pythonBridge.stdin.write(JSON.stringify(cmdObj) + "\n");
      return true;
    } catch (e) {
      console.error("[Python Bridge Write Error]", e);
    }
  }
  return false;
}

// Fallback execution for basic OS commands if bridge is not ready
function executeFallbackCommand(text) {
  const t = (text || "").trim();
  const lower = t.toLowerCase();
  let executed = false;
  let reply = `Executed: ${t}`;

  if (lower.includes("edge")) {
    exec("start msedge:");
    reply = "Opening Microsoft Edge";
    executed = true;
  } else if (lower.includes("notepad") || lower.includes("नोटपैड")) {
    exec("start notepad");
    reply = "Opening Notepad";
    executed = true;
  } else if (lower.includes("calc") || lower.includes("कैलकुलेटर")) {
    exec("start calc:");
    reply = "Opening Calculator";
    executed = true;
  } else if (lower.includes("chrome") || lower.includes("गूगल क्रोम")) {
    exec("start chrome");
    reply = "Opening Google Chrome";
    executed = true;
  } else if (lower.includes("time") || lower.includes("समय")) {
    const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    reply = lower.includes("समय") ? `वर्तमान समय ${timeStr} है।` : `The current time is ${timeStr}.`;
    executed = true;
  } else if (lower.includes("date") || lower.includes("तारीख") || lower.includes("दिनांक")) {
    const dateStr = new Date().toLocaleDateString([], { weekday: "long", year: "numeric", month: "long", day: "numeric" });
    reply = lower.includes("तारीख") || lower.includes("दिनांक") ? `आज की तारीख: ${dateStr}` : `Today is ${dateStr}.`;
    executed = true;
  } else if (lower.includes("screenshot") || lower.includes("स्क्रीनशॉट")) {
    exec("start ms-screenclip:");
    reply = "Opening Snipping Tool for screenshot";
    executed = true;
  } else if (lower.startsWith("search") || lower.startsWith("google") || lower.startsWith("खोजो")) {
    const query = t.replace(/^(search|google|खोजो)\s*(for)?\s*/i, "").trim();
    if (query) {
      exec(`start https://www.google.com/search?q=${encodeURIComponent(query)}`);
      reply = `Searching Google for: ${query}`;
      executed = true;
    }
  } else if (lower.startsWith("youtube") || lower.startsWith("play") || lower.includes("यूट्यूब")) {
    const query = t.replace(/^(youtube|play|यूट्यूब)\s*/i, "").trim();
    if (query) {
      exec(`start https://www.youtube.com/results?search_query=${encodeURIComponent(query)}`);
      reply = `Searching YouTube for: ${query}`;
    } else {
      exec("start https://www.youtube.com");
      reply = "Opening YouTube";
    }
    executed = true;
  } else if (lower.includes("help") || lower.includes("मदद")) {
    reply = "Supported actions: Open Notepad, Open Chrome, Open Edge, Calculator, Time, Date, Search <query>, YouTube <song>.";
    executed = true;
  } else {
    exec(`start https://www.google.com/search?q=${encodeURIComponent(t)}`);
    reply = `Searching for: ${t}`;
    executed = true;
  }

  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send("assistant-message", {
      success: executed,
      text: reply,
    });
    mainWindow.webContents.send("assistant-status", {
      state: "ready",
      text: "READY",
    });
  }
}

// ------------------------------------------------------------
// IPC DISPATCH HANDLERS
// ------------------------------------------------------------
ipcMain.on("send-command", (_, text) => {
  const ok = sendBridgeCommand({ type: "command", text });
  if (!ok) {
    executeFallbackCommand(text);
  }
});

ipcMain.on("start-listening", (_, opts) => {
  const lang = opts && opts.lang ? opts.lang : "auto";
  const ok = sendBridgeCommand({ type: "listen", lang });
  if (!ok && mainWindow) {
    mainWindow.webContents.send("standalone-voice", { lang });
  }
});

ipcMain.on("stop-listening", () => {
  sendBridgeCommand({ type: "stop" });
});

// Internal local HTTP bridge (silently handles port busy)
function startAssistantBridge() {
  const server = http.createServer((req, res) => {
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type");

    if (req.method === "OPTIONS") {
      res.writeHead(204);
      res.end();
      return;
    }

    const url = new URL(req.url, `http://${req.headers.host || "localhost:7878"}`);

    if (url.pathname === "/status" && req.method === "POST") {
      let body = "";
      req.on("data", (chunk) => (body += chunk));
      req.on("end", () => {
        try {
          const data = JSON.parse(body);
          if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send("assistant-status", data);
          }
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ ok: true }));
        } catch (e) {
          res.writeHead(400);
          res.end(JSON.stringify({ error: "Invalid JSON" }));
        }
      });
      return;
    }

    if (url.pathname === "/message" && req.method === "POST") {
      let body = "";
      req.on("data", (chunk) => (body += chunk));
      req.on("end", () => {
        try {
          const data = JSON.parse(body);
          if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send("assistant-message", data);
          }
          res.writeHead(200, { "Content-Type": "application/json" });
          res.end(JSON.stringify({ ok: true }));
        } catch (e) {
          res.writeHead(400);
          res.end(JSON.stringify({ error: "Invalid JSON" }));
        }
      });
      return;
    }

    res.writeHead(404);
    res.end();
  });

  server.on("error", (err) => {
    if (err.code === "EADDRINUSE") {
      // Port already in use by previous process, silently ignore
      return;
    }
  });

  try {
    server.listen(7878, "127.0.0.1");
  } catch (err) {}
}

// App lifecycle
app.whenReady().then(createWindow);

app.on("will-quit", () => {
  try {
    globalShortcut.unregisterAll();
  } catch (e) {}
});

app.on("before-quit", () => {
  if (pythonBridge) {
    try {
      pythonBridge.kill();
    } catch (e) {}
  }
  if (devUserData && fs.existsSync(devUserData)) {
    try {
      fs.rmSync(devUserData, { recursive: true, force: true });
    } catch (e) {}
  }
});

const cleanExit = () => {
  if (pythonBridge) {
    try {
      pythonBridge.kill();
    } catch (e) {}
  }
  app.quit();
};

process.on("SIGINT", cleanExit);
process.on("SIGTERM", cleanExit);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
