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
  window.URL.createObjectURL = () => "blob:http://lumen.test/test-media";
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
  window.HTMLMediaElement.prototype.canPlayType = (type) => type.startsWith("audio/") ? "probably" : "";
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

test("navigation, search, settings, repeat, and language controls respond", () => {
  const dom = bootRenderer({ library: ["/music/Blue.mp3", "/video/Night.mkv"] });
  const { document, Event, MouseEvent } = dom.window;

  document.querySelector('[data-page="library"]').click();
  assert.equal(document.querySelector("#pageHeading").textContent, "Library");
  assert.equal(document.querySelector("#libraryCount").textContent, "2 items in your library");
  const search = document.querySelector("#librarySearch");
  search.value = "blue";
  search.dispatchEvent(new Event("input", { bubbles: true }));
  assert.equal(document.querySelector("#libraryCount").textContent, "1 items in your library");
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
  document.querySelector("#repeatButton").click();
  assert.equal(document.querySelector("#repeatButton").classList.contains("selected"), true);
  assert.equal(document.querySelector("#repeatOneBadge").classList.contains("hidden"), true);
  dom.window.close();
});
