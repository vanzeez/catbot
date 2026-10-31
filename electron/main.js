// Electron shell: spawn the Python sidecar, wait for /api/stats, open the UI, global push-to-talk.
const { app, BrowserWindow, globalShortcut, session, systemPreferences } = require("electron");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const http = require("node:http");
const path = require("node:path");

const REPO = path.resolve(__dirname, "..");
const PORT = Number(process.env.CATBOT_PORT || 8765);
const URL = `http://127.0.0.1:${PORT}`;
const HOTKEY = "CommandOrControl+Alt+Space";
let sidecar = null;
let win = null;
let pttDown = false;

function pythonPath() {
  const win32 = path.join(REPO, ".venv", "Scripts", "python.exe");
  const posix = path.join(REPO, ".venv", "bin", "python");
  if (process.platform === "win32" && fs.existsSync(win32)) return win32;
  if (fs.existsSync(posix)) return posix;
  return process.platform === "win32" ? "python" : "python3";
}

function startSidecar() {
  const extra = (process.env.CATBOT_SIDECAR_ARGS || "").split(" ").filter(Boolean);  // e.g. "--fake"
  const args = ["-m", "catbot", "--serve", "--voice", ...extra];
  // Drop the npm_* variables `npm start` adds: nvm in the user's shell profile warns about them.
  const env = Object.fromEntries(Object.entries(process.env).filter(([k]) => !/^npm_/i.test(k)));
  sidecar = spawn(pythonPath(), args, { cwd: REPO, env: { ...env, CATBOT_PORT: String(PORT) } });
  sidecar.stdout.on("data", (d) => process.stdout.write(`[sidecar] ${d}`));
  sidecar.stderr.on("data", (d) => process.stdout.write(`[sidecar] ${d}`));
  sidecar.on("exit", (code) => { console.log(`[sidecar] exited ${code}`); sidecar = null; });
}

function waitForServer(timeoutMs = 30000) {
  const t0 = Date.now();
  return new Promise((resolve, reject) => {
    const tick = () => {
      http.get(`${URL}/api/stats`, (res) => {
        res.resume();
        if (res.statusCode === 200) return resolve();
        retry();
      }).on("error", retry);
    };
    const retry = () => (Date.now() - t0 > timeoutMs ? reject(new Error("sidecar did not start in 30 s")) : setTimeout(tick, 300));
    tick();
  });
}

function sendPtt(state) {
  if (!win) return;
  pttDown = state === "down";
  win.webContents.send("ptt", state);
}

async function createWindow() {
  session.defaultSession.setPermissionRequestHandler((wc, permission, cb) => {
    cb(permission === "media" && wc.getURL().startsWith(URL));
  });
  if (process.platform === "darwin") await systemPreferences.askForMediaAccess("microphone");
  win = new BrowserWindow({
    width: 1440, height: 900, minWidth: 1024, minHeight: 700, backgroundColor: "#0B0A10",
    title: "Catbot", webPreferences: {
      preload: path.join(__dirname, "preload.js"), contextIsolation: true,
      autoplayPolicy: "no-user-gesture-required",  // meow sounds and replies without a click first
    },
  });
  // Release detection only works while the window has focus; otherwise the hotkey toggles.
  win.webContents.on("before-input-event", (_e, input) => {
    if (pttDown && input.type === "keyUp" && input.code === "Space") sendPtt("up");
  });
  globalShortcut.register(HOTKEY, () => sendPtt(pttDown ? "up" : "down"));
  await win.loadURL(URL);
}

app.whenReady().then(async () => {
  startSidecar();
  try {
    await waitForServer();
  } catch (err) {
    console.error(String(err));
    app.quit();
    return;
  }
  await createWindow();
});

function stopSidecar() {
  if (sidecar) { sidecar.kill(); sidecar = null; }
}
app.on("window-all-closed", () => { stopSidecar(); app.quit(); });
app.on("will-quit", () => { globalShortcut.unregisterAll(); stopSidecar(); });
for (const sig of ["SIGINT", "SIGTERM"]) process.on(sig, () => { stopSidecar(); app.quit(); });
process.on("exit", stopSidecar);
