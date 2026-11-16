const API = window.lumen || null;
const IS_ELECTRON = Boolean(API);
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const DEFAULTS = { language: "system", library: [], volume: 80, speed: 1, repeat: 0, shuffle: false, ambient: true, volumeBoost: false, stableVolume: false, annotations: true, theme: "dark" };
const ICONS = {
  play: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m8 5 11 7-11 7z" fill="currentColor" stroke="none"/></svg>',
  pause: '<svg viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></svg>',
  settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="m19.4 15 .1.1 1.2.9-1.2 2.1-1.4-.6a8 8 0 0 1-1.8 1l-.2 1.5h-2.4l-.2-1.5a8 8 0 0 1-1.8-1l-1.4.6-1.2-2.1 1.2-.9a7 7 0 0 1 0-2l-1.2-.9 1.2-2.1 1.4.6a8 8 0 0 1 1.8-1l.2-1.5h2.4l.2 1.5a8 8 0 0 1 1.8 1l1.4-.6 1.2 2.1-1.2.9a7 7 0 0 1 0 2Z" transform="translate(-1 -1)"/></svg>',
  plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>',
  folder: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7.5A2.5 2.5 0 0 1 5.5 5H10l2 2h6.5A2.5 2.5 0 0 1 21 9.5v8a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z"/><path d="M3.5 10h17"/></svg>',
  library: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5.5A1.5 1.5 0 0 1 5.5 4H20v15H5.5A1.5 1.5 0 0 1 4 17.5z"/><path d="M4 6v12M8 8h8M8 12h8M8 16h5"/></svg>',
  shuffle: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="m16 3 4 4-4 4M4 7h2.5c4 0 6 10 10 10H20M16 13l4 4-4 4M4 17h2.5c1.2 0 2.2-1.3 3.1-2.9M13 8.6c1 1.7 2 3.4 3.5 3.4H20"/></svg>',
  previous: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M6 5v14M19 6l-9 6 9 6z" fill="currentColor" stroke="none"/></svg>',
  next: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M18 5v14M5 6l9 6-9 6z" fill="currentColor" stroke="none"/></svg>',
  repeat: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M17 2l4 4-4 4M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4M21 13v2a3 3 0 0 1-3 3H3"/></svg>',
  volume: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 10v4h4l5 4V6l-5 4zM17 9a5 5 0 0 1 0 6M19 6a9 9 0 0 1 0 12"/></svg>',
  mute: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 10v4h4l5 4V6l-5 4zM17 9l5 6M22 9l-5 6"/></svg>',
  fullscreen: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M8 4H4v4M16 4h4v4M4 16v4h4M20 16v4h-4"/></svg>',
  search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><circle cx="10.8" cy="10.8" r="6.5"/><path d="m16 16 4 4"/></svg>',
  video: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="13" height="14" rx="2"/><path d="m16 10 5-3v10l-5-3z"/></svg>',
  queue: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M4 6h16M4 11h13M4 16h10M4 21h7"/></svg>',
  close: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><path d="m6 6 12 12M18 6 6 18"/></svg>'
};
const FR = {
  "Now Playing": "En lecture", Player: "Lecteur", Library: "Bibliothèque", Settings: "Paramètres", "PLAY QUEUE": "FILE DE LECTURE",
  "Ready when you are": "À vous de choisir", "Add media": "Ajouter des médias", "Open a media file to begin": "Ouvrez un fichier média pour commencer",
  "Nothing playing": "Rien en lecture", "Your music and videos, in one place": "Vos musiques et vidéos, au même endroit",
  "Search your library": "Rechercher dans la bibliothèque", "Add files": "Ajouter des fichiers", "Add folder": "Ajouter un dossier",
  Preferences: "Préférences", Playback: "Lecture", "Default volume": "Volume par défaut", "Repeat queue": "Répéter la file",
  Shuffle: "Aléatoire", "Ambient visuals": "Visuels ambiants", "Volume boost": "Amplification du volume", "Stable volume": "Volume régulier",
  "Subtitles and annotations": "Sous-titres et annotations", "Software updates": "Mises à jour", "Check again": "Vérifier à nouveau",
  "Check for updates": "Vérifier les mises à jour", "Download update": "Télécharger la mise à jour", "Show download": "Afficher le fichier",
  Done: "Terminé", "items in your library": "éléments dans la bibliothèque", "Your queue is empty": "Votre file est vide",
  "Add a few files and they’ll show up here.": "Ajoutez des fichiers pour les voir ici.", "Toggle video fullscreen": "Plein écran vidéo",
  "Video is playing in Lumen": "La vidéo est en lecture dans Lumen", "This format is using the full mpv playback engine.": "Ce format utilise le moteur mpv.",
  "Playback speed": "Vitesse de lecture", "Nothing here yet": "Rien pour le moment", "Update available": "Mise à jour disponible",
  "You have the latest version": "Vous avez la dernière version", "Checking for updates…": "Recherche des mises à jour…",
  "Downloaded packages are installed manually; close Lumen, extract the ZIP, and replace the app files.": "Installez la mise à jour manuellement : fermez Lumen, décompressez le ZIP et remplacez l’application."
};

let state = { ...DEFAULTS };
let items = [];
let queueIndex = -1;
let mode = "idle";
let currentPath = "";
let currentItem = null;
let currentUrl = "";
let audioContext = null;
let analyser = null;
let mediaGraph = new WeakMap();
let mpvTimer = null;
let updateRelease = null;
let updateDownloaded = null;
let toastTimer = null;
let isSeeking = false;
let saveTimer = null;
let selectedPage = "player";
let lastVisualFrame = 0;
const video = $("#videoPlayer");
const audio = $("#audioPlayer");
const seekSlider = $("#seekSlider");
const volumeSlider = $("#volumeSlider");
const canvas = $("#visualizer");
const ctx = canvas.getContext("2d");

function tr(en) { return state.language === "fr" ? (FR[en] || en) : en; }
function localize() {
  $("#pageHeading").textContent = tr(selectedPage === "player" ? "Now Playing" : "Library");
  const navPlayer = document.querySelector('[data-page="player"] span:last-child');
  const navLibrary = document.querySelector('[data-page="library"] span:last-child');
  navPlayer.textContent = tr("Player"); navLibrary.textContent = tr("Library");
  $(".queue-heading .eyebrow").textContent = tr("PLAY QUEUE");
  $(".queue-heading h2").textContent = tr("Ready when you are");
  $(".queue-add span:last-child").textContent = tr("Add media");
  $("#trackTitle").textContent = currentItem ? currentItem.name : tr("Nothing playing");
  $("#trackPath").textContent = currentItem ? (currentItem.path || currentItem.file?.name || "") : tr("Your music and videos, in one place");
  $("#emptyState p").textContent = tr("Open a media file to begin");
  $("#librarySearch").placeholder = tr("Search your library");
  $("#settingsTitle").textContent = tr("Settings");
  $(".settings-group:first-child h3").textContent = tr("Preferences");
  $(".settings-group:nth-child(2) h3").textContent = tr("Playback");
  $(".update-heading h3").textContent = tr("Software updates");
  $("#checkUpdatesButton").textContent = tr("Check again");
  $("#downloadUpdateButton").textContent = tr("Download update");
  $("#showUpdateButton").textContent = tr("Show download");
  $("#doneSettings").textContent = tr("Done");
  $(".update-hint").textContent = tr("Downloaded packages are installed manually; close Lumen, extract the ZIP, and replace the app files.");
}

function installIcons() {
  $$('[data-icon]').forEach((node) => { node.innerHTML = ICONS[node.dataset.icon] || ""; });
}
function setIcon(button, name) {
  const icon = button?.querySelector("[data-icon]");
  if (icon) { icon.dataset.icon = name; icon.innerHTML = ICONS[name] || ""; }
}
function notify(message, isError = false) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.add("hidden"), 2400);
}
function prettyTime(value) {
  const seconds = Math.max(0, Math.floor(Number(value) || 0));
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;
  return hours ? `${hours}:${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}` : `${mins}:${String(secs).padStart(2, "0")}`;
}
function normalizePath(filePath) { return String(filePath || "").replaceAll("\\", "/").toLocaleLowerCase(); }
function itemForPath(filePath, file = null) {
  const raw = String(filePath || file?.name || "");
  const basename = raw.split(/[\\/]/).pop() || "Media";
  const dot = basename.lastIndexOf(".");
  const ext = dot >= 0 ? basename.slice(dot + 1).toUpperCase() : "MEDIA";
  const name = dot >= 0 ? basename.slice(0, dot) : basename;
  const audioExt = new Set(["MP3", "FLAC", "WAV", "OGG", "OGA", "OPUS", "M4A", "AAC", "WMA", "AIFF", "AIF", "APE", "AC3", "AMR", "WV"]);
  return { path: file ? `browser://${file.name}` : raw, realPath: file ? "" : raw, name, extension: ext, kind: audioExt.has(ext) ? "audio" : "video", file };
}
function persist() {
  state.library = items.filter((item) => !item.path.startsWith("browser://")).map((item) => item.path);
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    if (API) API.saveState(state).catch(() => {});
    else localStorage.setItem("lumen-state", JSON.stringify({ ...state, library: state.library }));
  }, 180);
}
function addPaths(paths, files = []) {
  const fileMap = new Map();
  for (const file of files) {
    fileMap.set(file.name, file);
    if (file.webkitRelativePath) fileMap.set(file.webkitRelativePath, file);
  }
  const seen = new Set(items.map((item) => normalizePath(item.path)));
  let added = 0;
  for (const path of paths) {
    const file = fileMap.get(path) || fileMap.get(String(path).split(/[\\/]/).pop());
    const item = itemForPath(file ? `browser://${file.webkitRelativePath || file.name}` : path, file);
    const key = normalizePath(item.path);
    if (!seen.has(key)) { seen.add(key); items.push(item); added++; }
  }
  renderQueue(); renderLibrary(); persist();
  if (added) notify(`${added} ${added === 1 ? "item" : "items"} added`);
}
async function chooseFiles() {
  if (API) {
    try {
      const paths = await API.openFiles();
      if (paths.length) { addPaths(paths); if (mode === "idle") playPath(paths[0]); }
    } catch (error) { showError(error.message); }
  } else { $("#browserFileInput").click(); }
}
async function chooseFolder() {
  if (API) {
    $("#scanStatus").classList.remove("hidden");
    try {
      const paths = await API.openFolder();
      if (paths.length) addPaths(paths);
      else if (!paths) notify("Folder scan finished");
    } catch (error) { showError(error.message); }
    finally { $("#scanStatus").classList.add("hidden"); }
  } else { $("#browserFolderInput").click(); }
}
function getSource(item) {
  if (item.file) return URL.createObjectURL(item.file);
  return API ? API.fileUrl(item.realPath || item.path) : "";
}
function canPlayInBrowser(item, element) {
  const ext = `.${item.extension.toLowerCase()}`;
  const mime = item.kind === "audio" ? ({".mp3":"audio/mpeg",".wav":"audio/wav",".ogg":"audio/ogg",".oga":"audio/ogg",".opus":"audio/ogg",".m4a":"audio/mp4",".aac":"audio/aac",".flac":"audio/flac"}[ext]) : ({".mp4":"video/mp4",".m4v":"video/mp4",".webm":"video/webm",".ogv":"video/ogg"}[ext]);
  return Boolean(mime && element.canPlayType(mime));
}
function loadMediaElement(element, item) {
  if (currentUrl && currentUrl.startsWith("blob:")) URL.revokeObjectURL(currentUrl);
  currentUrl = getSource(item);
  element.src = currentUrl;
  element.load();
}
async function initAudioGraph(element) {
  if (!window.AudioContext && !window.webkitAudioContext) return null;
  if (!audioContext) audioContext = new (window.AudioContext || window.webkitAudioContext)();
  if (!mediaGraph.has(element)) {
    const source = audioContext.createMediaElementSource(element);
    const compressor = audioContext.createDynamicsCompressor();
    const gain = audioContext.createGain();
    const meter = audioContext.createAnalyser();
    meter.fftSize = 128;
    compressor.threshold.value = 0;
    compressor.knee.value = 0;
    compressor.ratio.value = 1;
    compressor.attack.value = 0.003;
    compressor.release.value = 0.18;
    source.connect(compressor); compressor.connect(gain); gain.connect(meter); meter.connect(audioContext.destination);
    mediaGraph.set(element, { source, compressor, gain, meter });
  }
  analyser = mediaGraph.get(element).meter;
  if (audioContext.state === "suspended") await audioContext.resume();
  applyAudioSettings(element);
  return mediaGraph.get(element);
}
function applyAudioSettings(element) {
  const graph = mediaGraph.get(element);
  if (graph) {
    graph.gain.gain.value = Math.min(state.volume / 100, state.volumeBoost ? 1.3 : 1);
    graph.compressor.threshold.value = state.stableVolume ? -18 : 0;
    graph.compressor.knee.value = state.stableVolume ? 18 : 0;
    graph.compressor.ratio.value = state.stableVolume ? 4 : 1;
  } else if (element) {
    element.volume = Math.min(state.volume / 100, 1);
  }
  if (element && "playbackRate" in element) element.playbackRate = Number(state.speed) || 1;
}
function stopMpvPoll() { clearInterval(mpvTimer); mpvTimer = null; }
function startMpvPoll() {
  stopMpvPoll();
  mpvTimer = setInterval(async () => {
    if (mode !== "mpv" || !API) return;
    try {
      const s = await API.mpvState();
      if (!s.running) return;
      updateProgress(s.position, s.duration);
      if ($("#playButton").dataset.paused !== String(s.paused)) setPausedState(s.paused);
      if (s.eof) endedPlayback();
    } catch {}
  }, 360);
}
function setPausedState(paused) {
  $("#playButton").dataset.paused = String(paused);
  $("#playButton").setAttribute("aria-label", paused ? "Play" : "Pause");
  setIcon($("#playButton"), paused ? "play" : "pause");
  $("#stageMode").textContent = paused ? "PAUSED" : (mode === "mpv" ? "MPV PLAYER" : "PLAYING");
}
function updateProgress(position, duration) {
  const d = Math.max(0, Number(duration) || 0);
  const p = Math.max(0, Math.min(d || Infinity, Number(position) || 0));
  $("#currentTime").textContent = prettyTime(p);
  $("#durationTime").textContent = prettyTime(d);
  seekSlider.max = String(Math.max(1, Math.floor(d * 10)));
  if (!isSeeking) seekSlider.value = String(Math.floor(p * 10));
  const pct = d ? `${Math.max(0, Math.min(100, p / d * 100))}%` : "0%";
  seekSlider.style.setProperty("--range", pct);
  $("#seekSlider").disabled = !d;
}
function setVolume(value, save = true) {
  const max = state.volumeBoost ? 130 : 100;
  state.volume = Math.max(0, Math.min(max, Number(value) || 0));
  volumeSlider.max = String(max);
  volumeSlider.value = String(state.volume);
  volumeSlider.style.setProperty("--range", `${state.volume / max * 100}%`);
  $("#volumeLabel").textContent = `${Math.round(state.volume)}%`;
  $("#settingsVolume").max = String(max);
  $("#settingsVolume").value = String(state.volume);
  $("#settingsVolumeLabel").textContent = `${Math.round(state.volume)}%`;
  setIcon($("#muteButton"), state.volume <= 0 ? "mute" : "volume");
  if (mode === "mpv" && API) API.mpvCommand("volume", state.volume).catch(() => {});
  else { applyAudioSettings(mode === "audio" ? audio : video); }
  if (save) persist();
}
function renderQueue() {
  const list = $("#queueList"); list.replaceChildren();
  $("#queueCount").textContent = String(items.length);
  $("#queueEmpty").classList.toggle("hidden", items.length > 0);
  list.classList.toggle("hidden", items.length === 0);
  for (let index = 0; index < items.length; index++) {
    const item = items[index];
    const row = document.createElement("div"); row.className = `queue-item${index === queueIndex ? " current" : ""}`;
    const type = document.createElement("span"); type.className = "queue-type"; type.innerHTML = ICONS[item.kind === "audio" ? "volume" : "video"];
    const copy = document.createElement("span"); copy.className = "queue-info";
    const title = document.createElement("span"); title.className = "queue-name"; title.textContent = item.name;
    const sub = document.createElement("span"); sub.className = "queue-sub"; sub.textContent = item.extension;
    copy.append(title, sub);
    const play = document.createElement("button"); play.className = "queue-remove"; play.title = "Play this item"; play.textContent = "▶";
    play.addEventListener("click", (event) => { event.stopPropagation(); playPath(item.path); });
    const remove = document.createElement("button"); remove.className = "queue-remove"; remove.title = "Remove from queue"; remove.textContent = "×";
    remove.addEventListener("click", (event) => { event.stopPropagation(); removeItem(index); });
    row.append(type, copy, play, remove);
    row.addEventListener("click", () => playPath(item.path));
    list.append(row);
  }
}
function removeItem(index) {
  const [removed] = items.splice(index, 1);
  if (removed?.path === currentPath) stopPlayback();
  if (index < queueIndex) queueIndex--;
  if (queueIndex >= items.length) queueIndex = items.length - 1;
  renderQueue(); renderLibrary(); persist();
}
function renderLibrary() {
  const query = $("#librarySearch").value.trim().toLocaleLowerCase();
  const visible = items.filter((item) => `${item.name} ${item.extension} ${item.realPath}`.toLocaleLowerCase().includes(query));
  $("#libraryCount").textContent = `${visible.length} ${tr("items in your library")}`;
  $("#libraryEmpty").classList.toggle("hidden", visible.length > 0);
  $("#libraryList").classList.toggle("hidden", visible.length === 0);
  const list = $("#libraryList"); list.replaceChildren();
  const fragment = document.createDocumentFragment();
  for (const item of visible) {
    const row = document.createElement("button"); row.className = "library-row";
    const icon = document.createElement("span"); icon.className = "library-row-icon"; icon.innerHTML = ICONS[item.kind === "audio" ? "volume" : "video"];
    const copy = document.createElement("span"); copy.className = "library-row-copy";
    const name = document.createElement("span"); name.className = "library-row-name"; name.textContent = item.name;
    const path = document.createElement("span"); path.className = "library-row-path"; path.textContent = `${item.extension} · ${item.realPath || item.file?.name || "Local file"}`;
    copy.append(name, path);
    const play = document.createElement("span"); play.className = "secondary-button"; play.textContent = "Play";
    row.append(icon, copy, play); row.addEventListener("click", () => playPath(item.path));
    fragment.append(row);
  }
  list.append(fragment);
}
async function playPath(filePath) {
  const index = items.findIndex((item) => item.path === filePath);
  if (index < 0) return;
  const item = items[index];
  if (currentUrl && currentUrl.startsWith("blob:")) URL.revokeObjectURL(currentUrl);
  currentUrl = "";
  currentItem = item; currentPath = item.path; queueIndex = index;
  $("#trackTitle").textContent = item.name;
  $("#trackPath").textContent = item.realPath || item.file?.name || "Local media";
  $("#emptyState").classList.add("hidden");
  $("#playbackError").classList.add("hidden");
  $("#externalPlayback").classList.add("hidden");
  $("#stageMode").textContent = "LOADING";
  renderQueue();
  stopMpvPoll();
  const browserElement = item.kind === "audio" ? audio : video;
  const otherElement = item.kind === "audio" ? video : audio;
  video.classList.toggle("active", item.kind === "video");
  otherElement.pause(); otherElement.removeAttribute("src"); otherElement.load();
  if (mode === "mpv" && API) await API.mpvCommand("stop").catch(() => {});
  const htmlSupported = item.file ? item.kind === "audio" || item.kind === "video" : canPlayInBrowser(item, browserElement);
  if (!htmlSupported && API && item.realPath) {
    try {
      mode = "mpv";
      video.classList.remove("active"); video.pause(); video.removeAttribute("src");
      $("#mediaStage").classList.add("has-video");
      $("#visualizer").classList.toggle("hidden", item.kind !== "audio" || !state.ambient);
      $("#externalPlayback").classList.toggle("hidden", item.kind !== "video");
      await API.mpvOpen(item.realPath, state);
      await API.mpvCommand("volume-max", state.volumeBoost);
      await API.mpvCommand("volume", state.volume);
      await API.mpvCommand("speed", state.speed);
      setPausedState(false);
      startMpvPoll();
      if (item.kind === "video") API.mpvTracks().then(renderMpvTracks).catch(() => {});
      return;
    } catch (error) {
      mode = "idle";
      $("#externalPlayback").classList.add("hidden");
      showError(error.message || "The playback engine could not open that file.");
      return;
    }
  }
  mode = item.kind;
  $("#mediaStage").classList.toggle("has-video", item.kind === "video");
  $("#visualizer").classList.toggle("hidden", item.kind !== "audio" || !state.ambient);
  $("#externalPlayback").classList.add("hidden");
  browserElement.classList.add("active");
  browserElement.onloadedmetadata = () => {
    updateProgress(browserElement.currentTime, browserElement.duration);
    if (item.kind === "video") refreshHtmlTracks();
  };
  browserElement.onended = endedPlayback;
  browserElement.ontimeupdate = () => updateProgress(browserElement.currentTime, browserElement.duration);
  browserElement.onerror = () => {
    if (API && item.realPath) {
      mode = "idle";
      playPathExternalFallback(item);
    } else showError("This browser preview cannot decode this media format.");
  };
  browserElement.playbackRate = Number(state.speed) || 1;
  loadMediaElement(browserElement, item);
  try {
    await initAudioGraph(browserElement);
    await browserElement.play();
    setPausedState(false);
  } catch (error) {
    if (error.name === "NotAllowedError") notify("Press play to start audio");
    else showError(`Could not play this file: ${error.message}`);
  }
}
async function playPathExternalFallback(item) {
  try {
    mode = "mpv";
    video.classList.remove("active");
    $("#externalPlayback").classList.toggle("hidden", item.kind !== "video");
    $("#visualizer").classList.toggle("hidden", item.kind !== "audio" || !state.ambient);
    await API.mpvOpen(item.realPath, state);
    await API.mpvCommand("volume", state.volume);
    startMpvPoll();
    setPausedState(false);
  } catch (error) { showError(error.message); }
}
function stopPlayback() {
  stopMpvPoll();
  video.pause(); audio.pause(); video.classList.remove("active");
  video.removeAttribute("src"); audio.removeAttribute("src"); video.load(); audio.load();
  if (mode === "mpv" && API) API.mpvCommand("stop").catch(() => {});
  if (currentUrl?.startsWith("blob:")) URL.revokeObjectURL(currentUrl);
  currentUrl = ""; currentItem = null; currentPath = ""; mode = "idle"; queueIndex = -1;
  $("#trackTitle").textContent = tr("Nothing playing");
  $("#trackPath").textContent = tr("Your music and videos, in one place");
  $("#emptyState").classList.remove("hidden"); $("#externalPlayback").classList.add("hidden");
  $("#mediaStage").classList.remove("has-video"); $("#visualizer").classList.remove("hidden");
  $("#stageMode").textContent = "READY"; updateProgress(0, 0); renderQueue();
}
function togglePlay() {
  if (mode === "idle") { if (items.length) playPath(items[Math.max(0, queueIndex)]?.path || items[0].path); else chooseFiles(); return; }
  const paused = $("#playButton").dataset.paused === "true";
  if (mode === "mpv" && API) API.mpvCommand(paused ? "play" : "pause").catch((e) => showError(e.message));
  else {
    const element = mode === "audio" ? audio : video;
    if (paused) element.play().catch(() => {});
    else element.pause();
  }
  setPausedState(!paused);
}
function endedPlayback() {
  if (state.repeat === 2 && queueIndex >= 0) { playPath(items[queueIndex].path); return; }
  if (queueIndex + 1 < items.length) {
    const nextIndex = state.shuffle ? Math.floor(Math.random() * items.length) : queueIndex + 1;
    playPath(items[nextIndex].path);
  } else if (state.repeat === 1 && items.length) playPath(items[0].path);
  else setPausedState(true);
}
function playNext(direction = 1) {
  if (!items.length) return;
  let index = queueIndex;
  if (state.shuffle && items.length > 1 && direction > 0) index = Math.floor(Math.random() * items.length);
  else index = Math.max(0, Math.min(items.length - 1, (queueIndex < 0 ? 0 : queueIndex) + direction));
  playPath(items[index].path);
}
function seekTo(seconds) {
  const value = Math.max(0, Number(seconds) || 0);
  if (mode === "mpv" && API) API.mpvCommand("seek", value).catch(() => {});
  else if (mode === "audio") audio.currentTime = value;
  else if (mode === "video") video.currentTime = value;
}
function setSpeed(value) {
  state.speed = Math.max(.25, Math.min(3, Number(value) || 1));
  $("#speedSelect").value = String(state.speed);
  if (mode === "mpv" && API) API.mpvCommand("speed", state.speed).catch(() => {});
  else applyAudioSettings(mode === "audio" ? audio : video);
  persist(); notify(`Speed ${state.speed}×`);
}
function cycleRepeat() {
  state.repeat = (state.repeat + 1) % 3;
  $("#repeatButton").classList.toggle("selected", state.repeat > 0);
  $("#repeatOneBadge").classList.toggle("hidden", state.repeat !== 2);
  $("#repeatButton").title = ["Repeat off", "Repeat queue", "Repeat one"][state.repeat];
  persist(); notify(["Repeat off", "Repeat queue", "Repeat one"][state.repeat]);
}
function toggleShuffle() {
  state.shuffle = !state.shuffle;
  $("#shuffleButton").classList.toggle("selected", state.shuffle);
  persist(); notify(state.shuffle ? "Shuffle on" : "Shuffle off");
}
function toggleMute() {
  if (state.volume > 0) { state.lastVolume = state.volume; setVolume(0); }
  else setVolume(Math.max(1, Number(state.lastVolume) || 80));
}
function syncSettings() {
  $("#languageSelect").value = state.language;
  $("#repeatSetting").checked = state.repeat > 0;
  $("#shuffleSetting").checked = state.shuffle;
  $("#ambientSetting").checked = state.ambient;
  $("#boostSetting").checked = state.volumeBoost;
  $("#stableSetting").checked = state.stableVolume;
  $("#annotationsSetting").checked = state.annotations;
  $("#speedSelect").value = String(state.speed);
  $("#shuffleButton").classList.toggle("selected", state.shuffle);
  $("#repeatButton").classList.toggle("selected", state.repeat > 0);
  $("#repeatOneBadge").classList.toggle("hidden", state.repeat !== 2);
  setVolume(state.volume, false);
  localize();
}
function saveSettings() { persist(); }
function openSettings() { syncSettings(); $("#settingsOverlay").classList.remove("hidden"); $("#closeSettings").focus(); }
function closeSettings() { $("#settingsOverlay").classList.add("hidden"); $("#settingsButton").focus(); }
function showError(message) {
  $("#playbackError").textContent = String(message || "Playback failed.");
  $("#playbackError").classList.remove("hidden");
  notify(String(message || "Playback failed."), true);
}
function setPage(page) {
  selectedPage = page;
  $("#playerPage").classList.toggle("hidden", page !== "player");
  $("#libraryPage").classList.toggle("hidden", page !== "library");
  $$(".nav-item").forEach((button) => button.classList.toggle("active", button.dataset.page === page));
  localize();
}
function openTrackMenu(button, tracks, kind) {
  const menu = $("#trackMenu"); menu.replaceChildren();
  if (kind === "sub") {
    const off = document.createElement("button"); off.textContent = "Subtitles off"; off.addEventListener("click", () => selectTrack(kind, null)); menu.append(off);
  }
  tracks.forEach((track, index) => {
    const entry = document.createElement("button");
    entry.textContent = track.label || track.title || `${kind === "sub" ? "Subtitle" : "Audio"} ${index + 1}`;
    if (track.selected || (mode !== "mpv" && track.mode === "showing")) entry.classList.add("selected");
    entry.addEventListener("click", () => selectTrack(kind, track)); menu.append(entry);
  });
  const rect = button.getBoundingClientRect();
  menu.style.left = `${Math.min(rect.left, window.innerWidth - 205)}px`;
  menu.style.top = `${Math.max(8, rect.top - menu.offsetHeight - 10)}px`;
  menu.classList.remove("hidden");
  requestAnimationFrame(() => { menu.style.top = `${Math.max(8, rect.top - menu.offsetHeight - 8)}px`; });
}
async function selectTrack(kind, track) {
  $("#trackMenu").classList.add("hidden");
  if (mode === "mpv" && API) {
    const id = track ? Number(track.id) : null;
    await API.mpvCommand(kind === "sub" ? "sid" : "aid", id).catch((e) => showError(e.message));
  } else if (kind === "sub") {
    for (const textTrack of video.textTracks) textTrack.mode = track && textTrack === track.ref ? "showing" : "disabled";
  }
}
function refreshHtmlTracks() {
  const tracks = [...video.textTracks].map((track, i) => ({ id: i, label: track.label || track.language || `Subtitle ${i + 1}`, mode: track.mode, ref: track }));
  $("#subtitleButton").classList.toggle("hidden", tracks.length === 0 || !state.annotations);
  $("#subtitleButton").onclick = (event) => openTrackMenu(event.currentTarget, tracks, "sub");
}
function renderMpvTracks(tracks) {
  const audioTracks = tracks.filter((track) => track.type === "audio");
  const subtitleTracks = tracks.filter((track) => track.type === "sub");
  $("#audioTracksButton").classList.toggle("hidden", audioTracks.length < 2);
  $("#subtitleButton").classList.toggle("hidden", !state.annotations || subtitleTracks.length === 0);
  $("#audioTracksButton").onclick = (event) => openTrackMenu(event.currentTarget, audioTracks, "audio");
  $("#subtitleButton").onclick = (event) => openTrackMenu(event.currentTarget, subtitleTracks, "sub");
}
function updateScale() {
  const scale = Math.max(.75, Math.min(1.15, window.innerWidth / 1280, window.innerHeight / 800));
  document.documentElement.style.setProperty("--scale", scale.toFixed(3));
}
function drawVisualizer(timestamp = 0) {
  requestAnimationFrame(drawVisualizer);
  if (timestamp - lastVisualFrame < 32) return;
  lastVisualFrame = timestamp;
  const bounds = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  if (canvas.width !== Math.round(bounds.width * ratio) || canvas.height !== Math.round(bounds.height * ratio)) {
    canvas.width = Math.round(bounds.width * ratio); canvas.height = Math.round(bounds.height * ratio);
  }
  if (!bounds.width || !bounds.height || canvas.classList.contains("hidden")) return;
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, bounds.width, bounds.height);
  const active = mode === "audio" && $("#playButton").dataset.paused !== "true";
  const cx = bounds.width / 2, cy = bounds.height / 2;
  const scale = Math.min(1, bounds.width / 500, bounds.height / 350);
  const time = timestamp / 1000;
  const pulse = active ? (Math.sin(time * 2.2) + 1) / 2 : (Math.sin(time * .65) + 1) / 2 * .25;
  const glow = ctx.createRadialGradient(cx, cy, 30 * scale, cx, cy, 230 * scale);
  glow.addColorStop(0, `rgba(139,92,246,${.10 + pulse * .07})`); glow.addColorStop(1, "rgba(139,92,246,0)");
  ctx.fillStyle = glow; ctx.fillRect(0, 0, bounds.width, bounds.height);
  const width = 6 * scale, gap = 5 * scale, count = Math.max(12, Math.floor((bounds.width - 80) / (width + gap)));
  for (let i = 0; i < count; i++) {
    const wave = Math.abs(Math.sin(time * (active ? 2.8 : .7) + i * .51) * .56 + Math.cos(time * 1.3 + i * .29) * .44);
    const h = (4 + wave * (active ? 34 : 13)) * scale;
    const x = cx - (count * (width + gap)) / 2 + i * (width + gap);
    ctx.fillStyle = `rgba(52,232,192,${.12 + wave * .32})`;
    ctx.beginPath(); ctx.roundRect(x, bounds.height - 24 * scale - h, width, h, width / 2); ctx.fill();
  }
  ctx.beginPath(); ctx.arc(cx, cy, (52 + pulse * 2) * scale, 0, Math.PI * 2); ctx.fillStyle = "rgba(52,232,192,.13)"; ctx.fill();
}
async function checkForUpdates() {
  const status = $("#updateStatus"); status.className = "update-status"; status.textContent = tr("Checking for updates…");
  $("#downloadUpdateButton").classList.add("hidden"); $("#showUpdateButton").classList.add("hidden");
  try {
    if (!API) throw new Error("Open the installed desktop app to check for releases.");
    const result = await API.checkUpdate();
    if (result.current) {
      status.textContent = `${tr("You have the latest version")} · v${result.version}`; status.classList.add("ok");
      updateRelease = null; return;
    }
    updateRelease = result.release;
    status.textContent = `${tr("Update available")} · v${updateRelease.version}`;
    $("#downloadUpdateButton").classList.remove("hidden");
    const link = document.createElement("button"); link.className = "track-link"; link.textContent = tr("Release notes");
    link.addEventListener("click", () => API.openExternal(updateRelease.pageUrl));
    status.append(" ", link);
  } catch (error) {
    status.textContent = error.message || "Could not check for updates."; status.classList.add("error");
  }
}
async function downloadUpdate() {
  if (!API || !updateRelease) return;
  $("#downloadUpdateButton").disabled = true;
  $("#downloadUpdateButton").textContent = "Downloading…";
  $("#updateStatus").textContent = `Downloading ${updateRelease.assetName}…`;
  try {
    updateDownloaded = await API.downloadUpdate(updateRelease);
    $("#updateStatus").textContent = `Downloaded v${updateDownloaded.version} to Downloads.`;
    $("#updateStatus").className = "update-status ok";
    $("#showUpdateButton").classList.remove("hidden");
    notify(`Lumen v${updateDownloaded.version} downloaded`);
  } catch (error) {
    $("#updateStatus").textContent = error.message || "Update download failed.";
    $("#updateStatus").className = "update-status error";
  } finally {
    $("#downloadUpdateButton").disabled = false;
    $("#downloadUpdateButton").textContent = tr("Download update");
  }
}
function showDownloadedUpdate() {
  if (updateDownloaded && API) API.revealFile(updateDownloaded.path);
}

function wireEvents() {
  $("#addMediaButton").onclick = chooseFiles; $("#openMediaButton").onclick = chooseFiles; $("#queueAddButton").onclick = chooseFiles;
  $("#libraryAddFiles").onclick = chooseFiles; $("#libraryEmptyAdd").onclick = chooseFiles;
  $("#scanFolderButton").onclick = chooseFolder; $("#libraryAddFolder").onclick = chooseFolder;
  $("#settingsButton").onclick = openSettings; $("#closeSettings").onclick = closeSettings; $("#doneSettings").onclick = closeSettings;
  $("#settingsOverlay").addEventListener("click", (event) => { if (event.target === $("#settingsOverlay")) closeSettings(); });
  $$(".nav-item").forEach((button) => button.addEventListener("click", () => setPage(button.dataset.page)));
  $("#playButton").onclick = togglePlay; $("#previousButton").onclick = () => playNext(-1); $("#nextButton").onclick = () => playNext(1);
  $("#shuffleButton").onclick = toggleShuffle; $("#repeatButton").onclick = cycleRepeat;
  $("#muteButton").onclick = toggleMute; $("#fullscreenButton").onclick = async () => {
    try {
      if (mode === "mpv" && API) await API.mpvCommand("fullscreen");
      else if (video.classList.contains("active") && video.requestFullscreen) await video.requestFullscreen();
      else if (!document.fullscreenElement) await document.documentElement.requestFullscreen(); else await document.exitFullscreen();
    } catch { await document.documentElement.requestFullscreen?.().catch(() => {}); }
  };
  $("#focusExternalButton").onclick = () => { if (API && mode === "mpv") API.mpvCommand("fullscreen").catch(() => {}); };
  seekSlider.addEventListener("input", () => { isSeeking = true; $("#currentTime").textContent = prettyTime(Number(seekSlider.value) / 10); });
  seekSlider.addEventListener("change", () => { seekTo(Number(seekSlider.value) / 10); isSeeking = false; });
  volumeSlider.addEventListener("input", () => setVolume(volumeSlider.value));
  $("#settingsVolume").addEventListener("input", () => setVolume($("#settingsVolume").value));
  $("#speedSelect").addEventListener("change", () => setSpeed($("#speedSelect").value));
  $("#librarySearch").addEventListener("input", renderLibrary);
  $("#languageSelect").addEventListener("change", (event) => { state.language = event.target.value; localize(); persist(); });
  $("#repeatSetting").addEventListener("change", () => { state.repeat = $("#repeatSetting").checked ? (state.repeat || 1) : 0; syncSettings(); persist(); });
  $("#shuffleSetting").addEventListener("change", () => { state.shuffle = $("#shuffleSetting").checked; syncSettings(); persist(); });
  $("#ambientSetting").addEventListener("change", () => { state.ambient = $("#ambientSetting").checked; $("#visualizer").classList.toggle("hidden", mode !== "audio" || !state.ambient); persist(); });
  $("#boostSetting").addEventListener("change", () => {
    state.volumeBoost = $("#boostSetting").checked;
    if (!state.volumeBoost && state.volume > 100) state.volume = 100;
    setVolume(state.volume); if (mode === "mpv" && API) API.mpvCommand("volume-max", state.volumeBoost).catch(() => {}); persist();
  });
  $("#stableSetting").addEventListener("change", () => {
    state.stableVolume = $("#stableSetting").checked;
    if (mode === "mpv" && API) API.mpvCommand("stable-volume", state.stableVolume).catch(() => {});
    else applyAudioSettings(mode === "audio" ? audio : video);
    persist();
  });
  $("#annotationsSetting").addEventListener("change", () => {
    state.annotations = $("#annotationsSetting").checked;
    if (mode === "mpv" && API) API.mpvCommand("annotations", state.annotations).catch(() => {});
    if (mode === "video") refreshHtmlTracks();
    persist();
  });
  $("#checkUpdatesButton").onclick = checkForUpdates; $("#downloadUpdateButton").onclick = downloadUpdate; $("#showUpdateButton").onclick = showDownloadedUpdate;
  $("#browserFileInput").addEventListener("change", (event) => {
    const files = [...event.target.files];
    const paths = files.map((file) => file.webkitRelativePath || file.name);
    addPaths(paths, files);
    if (files[0]) playPath(`browser://${files[0].webkitRelativePath || files[0].name}`);
    event.target.value = "";
  });
  $("#browserFolderInput").addEventListener("change", (event) => {
    const files = [...event.target.files];
    const paths = files.map((file) => file.webkitRelativePath || file.name);
    addPaths(paths, files);
    if (files[0] && mode === "idle") playPath(`browser://${files[0].webkitRelativePath || files[0].name}`);
    event.target.value = "";
  });
  document.addEventListener("click", (event) => { if (!event.target.closest("#trackMenu") && !event.target.closest("#audioTracksButton") && !event.target.closest("#subtitleButton")) $("#trackMenu").classList.add("hidden"); });
  document.addEventListener("wheel", (event) => {
    if (!event.target.closest("#mediaStage") || event.target.closest("input,select,button")) return;
    event.preventDefault(); setVolume(state.volume + (event.deltaY < 0 ? 4 : -4));
  }, { passive: false });
  window.addEventListener("resize", updateScale);
  window.addEventListener("dragover", (event) => { event.preventDefault(); });
  window.addEventListener("drop", async (event) => {
    event.preventDefault();
    const files = [...(event.dataTransfer?.files || [])];
    const paths = [];
    for (const file of files) {
      const filePath = API ? API.pathForFile(file) : "";
      if (filePath) paths.push(filePath);
      else paths.push(file.name);
    }
    if (paths.length) {
      const mediaFiles = [];
      for (const filePath of paths) {
        if (API && !/\\.[^\\/]+$/.test(filePath)) {
          try { mediaFiles.push(...await API.scanFolder(filePath)); } catch {}
        } else mediaFiles.push(filePath);
      }
      addPaths(mediaFiles, API ? [] : files);
      if (mediaFiles.length && mode === "idle") playPath(mediaFiles[0]);
    }
  });
  window.addEventListener("keydown", (event) => {
    if (event.target.matches("input,textarea,select") || !$("#settingsOverlay").classList.contains("hidden")) {
      if (event.key === "Escape") closeSettings(); return;
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "o") { event.preventDefault(); chooseFiles(); }
    else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); setPage("library"); $("#librarySearch").focus(); }
    else if (event.code === "Space") { event.preventDefault(); togglePlay(); }
    else if (event.key === "ArrowRight") { event.preventDefault(); seekTo(Number(seekSlider.value) / 10 + 10); }
    else if (event.key === "ArrowLeft") { event.preventDefault(); seekTo(Math.max(0, Number(seekSlider.value) / 10 - 10)); }
    else if (event.key === "ArrowUp") { event.preventDefault(); setVolume(state.volume + 5); }
    else if (event.key === "ArrowDown") { event.preventDefault(); setVolume(state.volume - 5); }
    else if (event.key.toLowerCase() === "m") toggleMute();
    else if (event.key.toLowerCase() === "f") $("#fullscreenButton").click();
    else if (event.key.toLowerCase() === "n") playNext(1);
    else if (event.key.toLowerCase() === "p") playNext(-1);
  });
  video.addEventListener("play", () => { if (mode === "video") setPausedState(false); });
  video.addEventListener("pause", () => { if (mode === "video" && !video.ended) setPausedState(true); });
  audio.addEventListener("play", () => { if (mode === "audio") setPausedState(false); });
  audio.addEventListener("pause", () => { if (mode === "audio" && !audio.ended) setPausedState(true); });
}

async function initialize() {
  installIcons();
  updateScale();
  wireEvents();
  if (API) {
    try {
      state = { ...DEFAULTS, ...(await API.loadState()) };
      const paths = Array.isArray(state.library) ? state.library : [];
      items = paths.map((filePath) => itemForPath(filePath)).filter((item) => item.kind !== "unknown");
      $("#appVersion").textContent = `v${await API.version()}`;
      API.onPlaybackError((message) => showError(message));
    } catch { state = { ...DEFAULTS }; }
  } else {
    try {
      const saved = JSON.parse(localStorage.getItem("lumen-state") || "{}");
      state = { ...DEFAULTS, ...saved };
      items = (Array.isArray(state.library) ? state.library : []).map((filePath) => itemForPath(filePath)).filter((item) => item.kind !== "unknown");
    } catch { state = { ...DEFAULTS }; items = []; }
  }
  syncSettings(); renderQueue(); renderLibrary(); drawVisualizer();
  if (API) checkForUpdates(); else { $("#updateStatus").textContent = "Update checks are available in the installed desktop app."; }
}

initialize();
