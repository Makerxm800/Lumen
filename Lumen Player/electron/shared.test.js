const test = require("node:test");
const assert = require("node:assert/strict");
const {
  MEDIA_EXTENSIONS,
  mediaKind,
  extensionOf,
  shouldUseBrowser,
  assetForPlatform,
  parseVersion,
  isNewerVersion,
  filterLibrary
} = require("./shared");

test("media extensions classify audio and video reliably", () => {
  assert.equal(mediaKind("C:\\Media\\movie.MKV"), "video");
  assert.equal(mediaKind("/music/track.FLAC"), "audio");
  assert.equal(mediaKind("/docs/readme.txt"), "unknown");
  assert.equal(extensionOf("C:\\Media\\movie.MKV"), ".mkv");
  assert.ok(MEDIA_EXTENSIONS.has(".opus"));
});

test("browser playback is limited to formats supported by Chromium", () => {
  assert.equal(shouldUseBrowser("song.mp3", (_kind, ext) => ext === ".mp3"), true);
  assert.equal(shouldUseBrowser("movie.mkv", () => true), false);
  assert.equal(shouldUseBrowser("song.flac", () => ""), false);
});

test("updater assets match supported OS and architecture", () => {
  assert.equal(assetForPlatform("win32", "x64"), "Lumen-Windows-x64.zip");
  assert.equal(assetForPlatform("darwin", "arm64"), "Lumen-macOS-arm64.zip");
  assert.equal(assetForPlatform("darwin", "x64"), "Lumen-macOS-x64.zip");
  assert.equal(assetForPlatform("linux", "x64"), null);
});

test("semantic version comparisons handle stable and pre-release tags", () => {
  assert.deepEqual(parseVersion("v1.2.3"), { parts: [1, 2, 3], prerelease: "" });
  assert.equal(isNewerVersion("1.10.0", "1.9.9"), true);
  assert.equal(isNewerVersion("1.2.3", "1.2.3-rc.1"), true);
  assert.equal(isNewerVersion("1.2.3-beta.2", "1.2.3-beta.10"), false);
  assert.equal(isNewerVersion("bad", "1.2.3"), false);
});

test("library filtering uses visible names and paths", () => {
  const library = [
    { path: "/music/blue.mp3", name: "Blue" },
    { path: "/video/night.mkv", name: "Night" }
  ];
  assert.equal(filterLibrary(library, "BLU").length, 1);
  assert.equal(filterLibrary(library, "video").length, 1);
  assert.equal(filterLibrary(library, "").length, 2);
});
