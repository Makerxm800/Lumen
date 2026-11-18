const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron");
const fs = require("node:fs");
const fsp = require("node:fs/promises");
const path = require("node:path");
const net = require("node:net");
const { spawn } = require("node:child_process");
const {
  MEDIA_EXTENSIONS,
  assetForPlatform,
  isNewerVersion,
  mediaKind
} = require("./shared");

const APP_VERSION = app.getVersion();
const SETTINGS_FILE = path.join(app.getPath("userData"), "library.json");
const MPV_PATH = process.platform === "win32"
  ? path.join(process.resourcesPath, "runtime", "mpv.exe")
  : null;
const DEFAULT_STATE = {
  language: "system",
  library: [],
  librarySort: "recent",
  volume: 80,
  speed: 1,
  repeat: 0,
  shuffle: false,
  ambient: true,
  volumeBoost: false,
  stableVolume: false,
  annotations: true,
  theme: "dark"
};

let mainWindow;
let mpvProcess;
let mpvSocketPath;
let mpvRequestId = 1;
let mpvTracksCache = [];

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 760,
    minHeight: 540,
    title: "Lumen Player",
    backgroundColor: "#0a0a11",
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  });
  mainWindow.loadFile(path.join(__dirname, "..", "renderer", "index.html"));
  mainWindow.once("ready-to-show", () => mainWindow.show());
  mainWindow.on("closed", () => { mainWindow = null; });
}

function getMpvExecutable() {
  if (process.platform === "win32") {
    if (fs.existsSync(MPV_PATH)) return MPV_PATH;
    return null;
  }
  const choices = ["/opt/homebrew/bin/mpv", "/usr/local/bin/mpv", "/opt/local/bin/mpv", "/usr/bin/mpv"];
  return choices.find((candidate) => fs.existsSync(candidate)) || "mpv";
}

function ipcAddress() {
  if (process.platform === "win32") return `\\\\.\\pipe\\lumen-electron-mpv-${process.pid}`;
  return path.join(app.getPath("temp"), `lumen-electron-mpv-${process.pid}.sock`);
}

function startMpv() {
  if (mpvProcess && mpvProcess.exitCode === null) return true;
  const executable = getMpvExecutable();
  if (!executable) throw new Error("The bundled mpv playback runtime is missing. Reinstall the Windows package.");
  mpvSocketPath = ipcAddress();
  if (process.platform !== "win32") { try { fs.rmSync(mpvSocketPath, { force: true }); } catch {} }
  const args = [
    `--input-ipc-server=${mpvSocketPath}`,
    "--idle=yes", "--keep-open=yes", "--no-terminal", "--title=Lumen Player",
    "--volume-max=130", "--autofit=960x540"
  ];
  mpvProcess = spawn(executable, args, {
    windowsHide: true,
    stdio: "ignore",
    cwd: path.dirname(executable)
  });
  mpvProcess.on("error", (error) => {
    if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send("playback-error", `Could not start mpv: ${error.message}`);
  });
  mpvProcess.on("exit", () => { mpvProcess = null; mpvTracksCache = []; });
  return true;
}

function mpvRequest(command, timeoutMs = 850) {
  if (!mpvProcess || mpvProcess.exitCode !== null) throw new Error("The playback engine is not running.");
  const payload = JSON.stringify({ command, request_id: mpvRequestId++ }) + "\n";
  return new Promise((resolve, reject) => {
    let finished = false;
    let data = "";
    let socket;
    let connectionAttempts = 0;
    const timeout = setTimeout(() => complete(new Error("mpv did not respond in time.")), timeoutMs);
    function connect() {
      if (finished) return;
      connectionAttempts++;
      socket = net.createConnection(mpvSocketPath);
      socket.once("connect", () => socket.write(payload));
      socket.on("data", (chunk) => {
        data += chunk.toString();
        const newline = data.indexOf("\n");
        if (newline >= 0) {
          try { complete(null, JSON.parse(data.slice(0, newline))); }
          catch { complete(new Error("mpv returned invalid playback data.")); }
        }
      });
      socket.once("error", (error) => {
        socket.destroy();
        if (connectionAttempts < 12 && !finished) setTimeout(connect, 40);
        else complete(error);
      });
    }
    function complete(error, result) {
      if (finished) return;
      finished = true;
      clearTimeout(timeout);
      socket.destroy();
      if (error) reject(error);
      else if (result?.error && result.error !== "success") reject(new Error(result.error));
      else resolve(result?.data);
    }
    connect();
  });
}

async function readState() {
  if (!mpvProcess || mpvProcess.exitCode !== null) return { running: false, tracks: [] };
  const [position, duration, paused] = await Promise.all([
    mpvRequest(["get_property", "time-pos"]),
    mpvRequest(["get_property", "duration"]),
    mpvRequest(["get_property", "pause"])
  ]);
  let eof = false;
  if (Number.isFinite(duration) && Number.isFinite(position) && position >= duration - 0.35) {
    eof = Boolean(await mpvRequest(["get_property", "eof-reached"]));
  }
  return { running: true, position: Number(position) || 0, duration: Number(duration) || 0, paused: Boolean(paused), eof, tracks: mpvTracksCache };
}

async function loadState() {
  try {
    const parsed = JSON.parse(await fsp.readFile(SETTINGS_FILE, "utf8"));
    return { ...DEFAULT_STATE, ...parsed, library: Array.isArray(parsed.library) ? parsed.library : [] };
  } catch {
    return { ...DEFAULT_STATE, library: [] };
  }
}

async function saveState(state) {
  if (!state || typeof state !== "object") return false;
  const safe = {
    ...DEFAULT_STATE,
    language: ["system", "en", "fr"].includes(state.language) ? state.language : "system",
    librarySort: ["recent", "name-asc", "name-desc", "type"].includes(state.librarySort) ? state.librarySort : "recent",
    volume: Math.max(0, Math.min(state.volumeBoost ? 130 : 100, Number(state.volume) || 0)),
    speed: Math.max(0.25, Math.min(3, Number(state.speed) || 1)),
    repeat: Math.max(0, Math.min(2, Number(state.repeat) || 0)),
    shuffle: Boolean(state.shuffle), ambient: Boolean(state.ambient),
    volumeBoost: Boolean(state.volumeBoost), stableVolume: Boolean(state.stableVolume),
    annotations: Boolean(state.annotations), theme: "dark",
    library: Array.isArray(state.library) ? [...new Set(state.library.filter((item) => typeof item === "string"))].slice(0, 20000) : []
  };
  await fsp.mkdir(path.dirname(SETTINGS_FILE), { recursive: true });
  const temporary = `${SETTINGS_FILE}.tmp`;
  await fsp.writeFile(temporary, JSON.stringify(safe, null, 2));
  await fsp.rename(temporary, SETTINGS_FILE);
  return true;
}

function listFile(file) {
  return {
    path: file,
    name: path.basename(file, path.extname(file)),
    extension: path.extname(file).slice(1).toUpperCase(),
    kind: mediaKind(file)
  };
}

async function scanFolder(root) {
  const found = [];
  const stack = [root];
  const skip = new Set(["node_modules", ".git", "windows", "$recycle.bin", "system volume information", "program files", "program files (x86)"]);
  while (stack.length && found.length < 20000) {
    const dir = stack.pop();
    let entries;
    try { entries = await fsp.readdir(dir, { withFileTypes: true }); } catch { continue; }
    for (const entry of entries) {
      if (entry.name.startsWith(".") || skip.has(entry.name.toLowerCase())) continue;
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) stack.push(full);
      else if (entry.isFile() && MEDIA_EXTENSIONS.has(path.extname(entry.name).toLowerCase())) found.push(full);
    }
  }
  return found;
}

function registerIpc() {
  ipcMain.handle("app:version", () => APP_VERSION);
  ipcMain.handle("app:state-load", loadState);
  ipcMain.handle("app:state-save", (_event, state) => saveState(state));
  ipcMain.handle("files:open", async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      title: "Add media to Lumen",
      properties: ["openFile", "multiSelections"],
      filters: [{ name: "Media", extensions: [...MEDIA_EXTENSIONS].map((ext) => ext.slice(1)) }, { name: "All files", extensions: ["*"] }]
    });
    return result.canceled ? [] : result.filePaths;
  });
  ipcMain.handle("files:folder", async () => {
    const result = await dialog.showOpenDialog(mainWindow, { title: "Add a media folder", properties: ["openDirectory"] });
    if (result.canceled || !result.filePaths[0]) return [];
    return scanFolder(result.filePaths[0]);
  });
  ipcMain.handle("files:scan", (_event, directory) => scanFolder(directory));
  ipcMain.handle("files:reveal", (_event, file) => {
    if (typeof file === "string" && path.isAbsolute(file)) shell.showItemInFolder(file);
  });
  ipcMain.handle("external:open", (_event, value) => {
    const url = new URL(String(value));
    if (url.protocol !== "https:") throw new Error("Only secure links can be opened.");
    return shell.openExternal(url.href);
  });
  ipcMain.handle("mpv:open", async (_event, file, config) => {
    if (typeof file !== "string" || !path.isAbsolute(file) || !fs.existsSync(file)) throw new Error("That media file is no longer available.");
    startMpv();
    await mpvRequest(["set_property", "volume-max", config?.volumeBoost ? 130 : 100]);
    await mpvRequest(["set_property", "speed", Number(config?.speed) || 1]);
    await mpvRequest(["set_property", "sid", config?.annotations === false ? "no" : "auto"]);
    if (config?.stableVolume) await mpvRequest(["af", "add", "@lumen:acompressor=threshold=0.12:ratio=3"]).catch(() => {});
    await mpvRequest(["loadfile", file, "replace"]);
    mpvTracksCache = [];
    return true;
  });
  ipcMain.handle("mpv:command", async (_event, operation, value) => {
    const allowed = new Set(["play", "pause", "toggle", "seek", "volume", "volume-max", "speed", "fullscreen", "sid", "aid", "annotations", "stable-volume", "stop"]);
    if (!allowed.has(operation)) throw new Error("That playback action is not supported.");
    if (!mpvProcess || mpvProcess.exitCode !== null) return false;
    switch (operation) {
      case "play": return mpvRequest(["set_property", "pause", false]);
      case "pause": return mpvRequest(["set_property", "pause", true]);
      case "toggle": return mpvRequest(["cycle", "pause"]);
      case "seek": return mpvRequest(["seek", Number(value) || 0, "absolute"]);
      case "volume": return mpvRequest(["set_property", "volume", Math.max(0, Math.min(130, Number(value) || 0))]);
      case "volume-max": return mpvRequest(["set_property", "volume-max", value ? 130 : 100]);
      case "speed": return mpvRequest(["set_property", "speed", Math.max(0.25, Math.min(3, Number(value) || 1))]);
      case "fullscreen": return mpvRequest(["cycle", "fullscreen"]);
      case "sid": return mpvRequest(["set_property", "sid", value === null ? "no" : Number(value)]);
      case "aid": return mpvRequest(["set_property", "aid", Number(value)]);
      case "annotations": return mpvRequest(["set_property", "sid", value ? "auto" : "no"]);
      case "stable-volume": {
        const args = value
          ? ["af", "add", "@lumen:acompressor=threshold=0.12:ratio=3"]
          : ["af", "remove", "@lumen"];
        return mpvRequest(args).catch(() => false);
      }
      case "stop": return mpvRequest(["stop"]);
    }
  });
  ipcMain.handle("mpv:state", async () => {
    if (!mpvProcess || mpvProcess.exitCode !== null) return { running: false, tracks: [] };
    try {
      const result = await readState();
      return result;
    } catch {
      return { running: Boolean(mpvProcess), tracks: mpvTracksCache };
    }
  });
  ipcMain.handle("mpv:tracks", async () => {
    if (!mpvProcess || mpvProcess.exitCode !== null) return [];
    const tracks = await mpvRequest(["get_property", "track-list"]);
    mpvTracksCache = Array.isArray(tracks) ? tracks.filter((track) => ["audio", "sub"].includes(track.type)).map((track) => ({
      id: track.id,
      type: track.type,
      selected: Boolean(track.selected),
      label: track.title || track.lang || `${track.type === "sub" ? "Subtitle" : "Audio"} ${track.id}`
    })) : [];
    return mpvTracksCache;
  });
  ipcMain.handle("mpv:stop", async () => {
    if (!mpvProcess || mpvProcess.exitCode !== null) return false;
    try { await mpvRequest(["quit"]); } catch { mpvProcess.kill(); }
    return true;
  });
  ipcMain.handle("update:check", checkForUpdate);
  ipcMain.handle("update:download", (_event, release) => downloadUpdate(release));
}

async function checkForUpdate() {
  const assetName = assetForPlatform(process.platform, process.arch);
  if (!assetName) throw new Error("Automatic downloads are available for Windows and macOS builds.");
  const response = await fetch("https://api.github.com/repos/Makerxm800/Lumen/releases/latest", {
    headers: { "User-Agent": "Lumen-Electron-Updater", "Accept": "application/vnd.github+json" }
  });
  if (!response.ok) throw new Error(`GitHub update check failed (${response.status}).`);
  const release = await response.json();
  const tag = release.tag_name;
  const version = String(tag || "").replace(/^v/, "");
  if (!version) throw new Error("The latest GitHub release has no version tag.");
  if (!isNewerVersion(version, APP_VERSION)) return { current: true, version: APP_VERSION };
  const asset = (release.assets || []).find((item) => item.name === assetName);
  if (!asset?.browser_download_url) throw new Error(`The latest release does not include ${assetName}.`);
  return { current: false, release: { version, pageUrl: release.html_url, assetName, assetUrl: asset.browser_download_url } };
}

async function downloadUpdate(release) {
  if (!release || typeof release.assetName !== "string" || typeof release.assetUrl !== "string") throw new Error("The update details are invalid.");
  const expected = assetForPlatform(process.platform, process.arch);
  const url = new URL(release.assetUrl);
  if (release.assetName !== expected || url.hostname !== "github.com" || !url.pathname.startsWith("/Makerxm800/Lumen/releases/download/")) {
    throw new Error("The update download link did not match this platform.");
  }
  const response = await fetch(url, { headers: { "User-Agent": "Lumen-Electron-Updater" }, redirect: "follow" });
  if (!response.ok) throw new Error(`Update download failed (${response.status}).`);
  const bytes = Buffer.from(await response.arrayBuffer());
  if (bytes.length < 1024 || bytes.length > 600 * 1024 * 1024) throw new Error("The update package looks incomplete or unexpectedly large.");
  const downloads = app.getPath("downloads");
  await fsp.mkdir(downloads, { recursive: true });
  const destination = path.join(downloads, release.assetName);
  const temp = `${destination}.part`;
  await fsp.writeFile(temp, bytes);
  await fsp.rm(destination, { force: true });
  await fsp.rename(temp, destination);
  return { path: destination, version: release.version, assetName: release.assetName };
}

app.whenReady().then(() => {
  registerIpc();
  createWindow();
  app.on("activate", () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});

app.on("before-quit", () => {
  if (mpvProcess && mpvProcess.exitCode === null) mpvProcess.kill();
  if (process.platform !== "win32" && mpvSocketPath) { try { fs.rmSync(mpvSocketPath, { force: true }); } catch {} }
});

app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
