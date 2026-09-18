/**
 * Starts the Iris voice assistant using the project virtualenv Python.
 * Usage (repo root): npm run dev
 */
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const winPython = path.join(root, ".venv", "Scripts", "python.exe");
const unixPython = path.join(root, ".venv", "bin", "python");

let python;
if (process.platform === "win32" && fs.existsSync(winPython)) {
  python = winPython;
} else if (fs.existsSync(unixPython)) {
  python = unixPython;
} else {
  console.error("Missing .venv. Create it and install deps first:");
  console.error("  python -m venv .venv");
  console.error("  .venv\\Scripts\\python.exe -m pip install -r requirements.txt");
  process.exit(1);
}

const assistant = path.join(root, "assistant.py");
if (!fs.existsSync(assistant)) {
  console.error("assistant.py not found in the repo root.");
  process.exit(1);
}

console.log("Starting Iris voice assistant...");
console.log(`Python: ${python}`);
console.log("Stop with Ctrl+C\n");

const child = spawn(python, ["-u", "assistant.py"], {
  cwd: root,
  stdio: "inherit",
  env: {
    ...process.env,
    PYTHONUNBUFFERED: "1",
    PYGAME_HIDE_SUPPORT_PROMPT: "1",
  },
  windowsHide: false,
});

child.on("error", (err) => {
  console.error("Failed to start assistant:", err.message);
  process.exit(1);
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.exit(0);
  }
  process.exit(code ?? 0);
});

function shutdown() {
  if (child.exitCode !== null) return;
  child.kill("SIGINT");
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
