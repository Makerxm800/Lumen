const { contextBridge, ipcRenderer, webUtils } = require("electron");
const { pathToFileURL } = require("node:url");

contextBridge.exposeInMainWorld("lumen", Object.freeze({
  version: () => ipcRenderer.invoke("app:version"),
  loadState: () => ipcRenderer.invoke("app:state-load"),
  saveState: (state) => ipcRenderer.invoke("app:state-save", state),
  openFiles: () => ipcRenderer.invoke("files:open"),
  openFolder: () => ipcRenderer.invoke("files:folder"),
  scanFolder: (directory) => ipcRenderer.invoke("files:scan", directory),
  revealFile: (file) => ipcRenderer.invoke("files:reveal", file),
  openExternal: (url) => ipcRenderer.invoke("external:open", url),
  fileUrl: (file) => pathToFileURL(file).href,
  pathForFile: (file) => webUtils.getPathForFile(file),
  mpvOpen: (file, options) => ipcRenderer.invoke("mpv:open", file, options),
  mpvCommand: (operation, value) => ipcRenderer.invoke("mpv:command", operation, value),
  mpvState: () => ipcRenderer.invoke("mpv:state"),
  mpvTracks: () => ipcRenderer.invoke("mpv:tracks"),
  mpvStop: () => ipcRenderer.invoke("mpv:stop"),
  checkUpdate: () => ipcRenderer.invoke("update:check"),
  downloadUpdate: (release) => ipcRenderer.invoke("update:download", release),
  onPlaybackError: (callback) => {
    const listener = (_event, message) => callback(String(message));
    ipcRenderer.on("playback-error", listener);
    return () => ipcRenderer.removeListener("playback-error", listener);
  }
}));
