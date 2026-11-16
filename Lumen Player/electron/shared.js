const MEDIA_EXTENSIONS = new Set([
  ".mp4", ".m4v", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".flv", ".mpg", ".mpeg", ".m2ts", ".mts",
  ".ts", ".3gp", ".ogv", ".vob", ".asf", ".rm", ".rmvb", ".mp3", ".flac", ".wav", ".ogg", ".oga",
  ".opus", ".m4a", ".aac", ".wma", ".aiff", ".aif", ".ape", ".ac3", ".amr", ".wv"
]);

const BROWSER_VIDEO_EXTENSIONS = new Set([".mp4", ".m4v", ".webm", ".ogv"]);
const BROWSER_AUDIO_EXTENSIONS = new Set([".mp3", ".wav", ".ogg", ".oga", ".opus", ".m4a", ".aac", ".flac"]);

function mediaKind(filePath) {
  const ext = extensionOf(filePath);
  if ([".mp3", ".flac", ".wav", ".ogg", ".oga", ".opus", ".m4a", ".aac", ".wma", ".aiff", ".aif", ".ape", ".ac3", ".amr", ".wv"].includes(ext)) return "audio";
  if (MEDIA_EXTENSIONS.has(ext)) return "video";
  return "unknown";
}

function extensionOf(filePath) {
  const name = String(filePath || "").split(/[\\/]/).pop() || "";
  const index = name.lastIndexOf(".");
  return index >= 0 ? name.slice(index).toLowerCase() : "";
}

function shouldUseBrowser(filePath, canPlayType) {
  const ext = extensionOf(filePath);
  const kind = mediaKind(filePath);
  if (kind === "audio" && BROWSER_AUDIO_EXTENSIONS.has(ext)) return Boolean(canPlayType("audio", ext));
  if (kind === "video" && BROWSER_VIDEO_EXTENSIONS.has(ext)) return Boolean(canPlayType("video", ext));
  return false;
}

function assetForPlatform(platform, arch) {
  if (platform === "win32" && arch === "x64") return "Lumen-Windows-x64.zip";
  if (platform === "darwin" && arch === "arm64") return "Lumen-macOS-arm64.zip";
  if (platform === "darwin" && arch === "x64") return "Lumen-macOS-x64.zip";
  return null;
}

function parseVersion(version) {
  const match = String(version).replace(/^v/i, "").match(/^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$/);
  if (!match) return null;
  return { parts: match.slice(1, 4).map(Number), prerelease: match[4] || "" };
}

function isNewerVersion(candidate, current) {
  const a = parseVersion(candidate);
  const b = parseVersion(current);
  if (!a || !b) return false;
  for (let i = 0; i < 3; i++) {
    if (a.parts[i] !== b.parts[i]) return a.parts[i] > b.parts[i];
  }
  if (!a.prerelease && b.prerelease) return true;
  if (a.prerelease && !b.prerelease) return false;
  return a.prerelease.localeCompare(b.prerelease, undefined, { numeric: true }) > 0;
}

function filterLibrary(paths, query) {
  const normalized = String(query || "").trim().toLocaleLowerCase();
  return paths.filter((entry) => {
    const path = typeof entry === "string" ? entry : entry.path;
    return normalized ? `${entry.name || ""} ${path}`.toLocaleLowerCase().includes(normalized) : true;
  });
}

module.exports = {
  MEDIA_EXTENSIONS,
  mediaKind,
  extensionOf,
  shouldUseBrowser,
  assetForPlatform,
  parseVersion,
  isNewerVersion,
  filterLibrary
};
