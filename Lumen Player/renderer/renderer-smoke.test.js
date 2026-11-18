const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { JSDOM } = require("jsdom");

const root = __dirname;
const html = fs.readFileSync(path.join(root, "index.html"), "utf8");
const script = fs.readFileSync(path.join(root, "app.js"), "utf8");

function bootRenderer(savedState = {}) {
  const dom = new JSDOM(html, { runScripts: "outside-only", url: "http://lumen.test/" });
  const { window } = dom;
  window.requestAnimationFrame = () => 1;
  let blobId = 0;
  window.URL.createObjectURL = () => `blob:http://lumen.test/media-${++blobId}`;
  window.URL.revokeObjectURL = () => {};
  window.HTMLCanvasElement.prototype.getContext = () => null;
  window.HTMLMediaElement.prototype.load = function () {};
  window.HTMLMediaElement.prototype.play = function () {
    this.dispatchEvent(new window.Event("play"));
    return Promise.resolve();
  };
  window.HTMLMediaElement.prototype.pause = function () {
    this.dispatchEvent(new window.Event("pause"));
  };
  window.HTMLMediaElement.prototype.canPlayType = (type) => /^(audio|video)\//.test(type) ? "probably" : "";
  window.localStorage.setItem("lumen-state", JSON.stringify(savedState));
  window.eval(script);
  return dom;
}

test("renderer boots with matching elements, no broken selectors, and an idle player", () => {
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
  assert.equal(new Set(ids).size, ids.length, "HTML element IDs must be unique");
  for (const [, selector] of script.matchAll(/\$\("#([^" ]+)"\)/g)) {
    assert.ok(ids.includes(selector), `renderer references missing #${selector}`);
  }

  const dom = bootRenderer();
  const { document } = dom.window;
  assert.equal(document.querySelector("#pageHeading").textContent, "Now Playing");
  assert.equal(document.querySelector("#trackTitle").textContent, "Nothing playing");
  assert.equal(document.querySelector("#queueCount").textContent, "0");
  assert.equal(document.querySelector("#libraryEmpty").classList.contains("hidden"), false);
  assert.equal(document.querySelector("#addMediaButton"), null, "file import belongs on the Library page");
  assert.equal(document.querySelector("#scanFolderButton"), null, "folder import belongs on the Library page");
  dom.window.close();
});

test("media selection and play/pause controls update the player state", async () => {
  const dom = bootRenderer();
  const { window } = dom;
  const file = new window.File(["test audio"], "tone.mp3", { type: "audio/mpeg" });
  const input = window.document.querySelector("#browserFileInput");
  Object.defineProperty(input, "files", { configurable: true, value: [file] });
  input.dispatchEvent(new window.Event("change", { bubbles: true }));
  await new Promise((resolve) => window.setTimeout(resolve, 0));

  assert.equal(window.document.querySelector("#trackTitle").textContent, "tone");
  assert.equal(window.document.querySelector("#playButton").dataset.paused, "false");
  window.document.querySelector("#playButton").click();
  assert.equal(window.document.querySelector("#playButton").dataset.paused, "true");
  dom.window.close();
});

test("seek thumbnail is isolated from captions and the custom speed menu updates playback", async () => {
  const dom = bootRenderer();
  const { document } = dom.window;
  const preview = document.querySelector("#seekPreviewSource");
  assert.ok(preview, "a separate, offscreen media source provides preview frames");
  assert.equal(preview.hidden, true);
  assert.equal(preview.hasAttribute("muted"), true);
  assert.equal(preview.querySelector("track"), null, "preview source must not attach subtitle tracks");
  assert.ok(document.querySelector("#seekPreviewCanvas"));
  assert.equal(document.querySelector("#annotationsButton"), null, "caption enhancement toggle is removed");
  assert.ok(document.querySelector("#subtitleButton"), "real subtitle-track controls remain available");

  const trigger = document.querySelector("#speedButton");
  const menu = document.querySelector("#speedMenu");
  trigger.click();
  assert.equal(menu.classList.contains("hidden"), false);
  assert.equal(trigger.getAttribute("aria-expanded"), "true");
  document.querySelector('#speedMenu [data-speed="1.5"]').click();
  assert.equal(document.querySelector("#speedLabel").textContent, "1.5×");
  assert.equal(document.querySelector('#speedMenu [data-speed="1.5"]').getAttribute("aria-checked"), "true");
  assert.equal(menu.classList.contains("hidden"), true);
  assert.equal(document.querySelector("#videoPlayer").playbackRate, 1.5);
  dom.window.close();
});

test("video zoom and split comparison controls are usable", async () => {
  const dom = bootRenderer();
  const { window } = dom;
  const files = [
    new window.File(["video one"], "one.mp4", { type: "video/mp4" }),
    new window.File(["video two"], "two.webm", { type: "video/webm" })
  ];
  const input = window.document.querySelector("#browserFileInput");
  Object.defineProperty(input, "files", { configurable: true, value: files });
  input.dispatchEvent(new window.Event("change", { bubbles: true }));
  await new Promise((resolve) => window.setTimeout(resolve, 0));

  assert.equal(window.document.querySelector("#stageTools").classList.contains("hidden"), false);
  window.document.querySelector("#zoomInButton").click();
  assert.equal(window.document.querySelector("#zoomReadout").textContent, "125%");
  window.document.querySelector("#zoomResetButton").click();
  const video = window.document.querySelector("#videoPlayer");
  const stage = window.document.querySelector("#mediaStage");
  const pointer = (type, pointerId, clientX, clientY) => {
    const event = new window.Event(type, { bubbles: true, cancelable: true });
    Object.assign(event, { pointerId, pointerType: "touch", clientX, clientY, button: 0 });
    return event;
  };
  video.dispatchEvent(pointer("pointerdown", 1, 100, 100));
  video.dispatchEvent(pointer("pointerdown", 2, 200, 100));
  stage.dispatchEvent(pointer("pointermove", 2, 250, 100));
  assert.equal(window.document.querySelector("#zoomReadout").textContent, "150%");
  stage.dispatchEvent(pointer("pointerup", 1, 100, 100));
  stage.dispatchEvent(pointer("pointerup", 2, 250, 100));
  window.document.querySelector("#splitButton").click();
  const compareSelect = window.document.querySelector("#compareSelect");
  assert.equal(compareSelect.classList.contains("hidden"), false);
  compareSelect.value = "browser://two.webm";
  compareSelect.dispatchEvent(new window.Event("change", { bubbles: true }));
  assert.equal(window.document.querySelector("#videoSplit").classList.contains("split-visible"), true);
  assert.equal(window.document.querySelector("#compareVideo").classList.contains("active"), true);
  dom.window.close();
});

test("navigation, search, settings, repeat, and language controls respond", async () => {
  const dom = bootRenderer({ library: ["/music/Blue.mp3", "/video/Night.mkv"] });
  const { document, Event, MouseEvent } = dom.window;

  document.querySelector('[data-page="library"]').click();
  assert.equal(document.querySelector("#pageHeading").textContent, "Library");
  assert.equal(document.querySelector("#libraryCount").textContent, "2 items");
  const sort = document.querySelector("#sortSelect");
  sort.value = "name-desc";
  sort.dispatchEvent(new Event("change", { bubbles: true }));
  assert.equal(document.querySelector(".library-row-name").textContent, "Night");
  const typeFilter = document.querySelector("#typeFilter");
  typeFilter.value = "audio";
  typeFilter.dispatchEvent(new Event("change", { bubbles: true }));
  assert.equal(document.querySelectorAll(".library-row").length, 1);
  const search = document.querySelector("#librarySearch");
  search.value = "blue";
  search.dispatchEvent(new Event("input", { bubbles: true }));
  assert.equal(document.querySelector("#libraryCount").textContent, "1 items · Audio");
  assert.equal(document.querySelectorAll(".library-row").length, 1);

  document.querySelector("#settingsButton").dispatchEvent(new MouseEvent("click", { bubbles: true }));
  assert.equal(document.querySelector("#settingsOverlay").classList.contains("hidden"), false);
  const language = document.querySelector("#languageSelect");
  language.value = "fr";
  language.dispatchEvent(new Event("change", { bubbles: true }));
  assert.equal(document.querySelector("#pageHeading").textContent, "Bibliothèque");
  assert.equal(document.querySelector("#settingsTitle").textContent, "Paramètres");

  document.querySelector("#closeSettings").click();
  assert.equal(document.querySelector("#settingsOverlay").classList.contains("hidden"), true);
  assert.equal(document.querySelector("#settingsVolume"), null, "volume belongs in the player controls, not settings");
  assert.equal(document.querySelectorAll(".toggle-row").length, 0, "playback toggles belong in the player controls");
  document.querySelector(".library-remove").click();
  assert.equal(document.querySelector("#queueCount").textContent, "1");
  await new Promise((resolve) => dom.window.setTimeout(resolve, 220));
  assert.deepEqual(JSON.parse(dom.window.localStorage.getItem("lumen-state")).library, ["/video/Night.mkv"]);
  document.querySelector("#repeatButton").click();
  assert.equal(document.querySelector("#repeatButton").classList.contains("selected"), true);
  assert.equal(document.querySelector("#repeatOneBadge").classList.contains("hidden"), true);
  dom.window.close();
});
