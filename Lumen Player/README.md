# Lumen Player — Rust desktop app

Lumen is a native Rust media player with a custom dark/purple interface based on the original Lumen look. On Windows, the video surface is embedded in the player window. mpv/FFmpeg supplies media decoding; the old Prism Player is not part of this app.

## Build a Windows executable

The Windows `.exe` must be built on Windows. Install the stable Rust toolchain with Cargo (`https://rustup.rs/`) and 7-Zip, then double-click `build_windows.bat`.

On the first build, the script downloads the latest baseline x64 portable mpv build from `shinchiro/mpv-winbuild-cmake` (about 30 MB), extracts it, compiles the Rust app, and packages the player runtime. Internet access is needed for this first build. The output is:

```text
dist/Lumen.exe
dist/runtime/   # mpv.exe, DLLs, plugins and notices from the portable build
```

Keep the `runtime` folder beside `Lumen.exe`; it is required for playback. To use a different mpv distribution, put its complete portable Windows runtime in `runtime/` before building. A signed installer can be made from the output with Inno Setup; no installer or signing certificate is included here.

## Run/build from source on macOS or Linux

Install Rust/Cargo and mpv, then run from this folder:

```bash
cargo run --manifest-path rust/Cargo.toml
```

The app searches for mpv in `runtime/`, beside the Lumen executable, or on `PATH`. On Windows, the build embeds the video output in the custom player surface. On macOS/Linux, playback uses mpv's native video window.

## Playback and features

The bundled mpv runtime uses FFmpeg and supports a broad range of common video/music containers and codecs (MP4, MKV, MOV, AVI, WebM, MP3, FLAC, WAV, AAC, Ogg, Opus, and others enabled in that build). Codec support depends on the runtime; DRM-protected, damaged, and unusual formats are not guaranteed.

The Rust app includes a custom animated interface, embedded Windows video surface, audio playback, persistent media library and queue, drag-and-drop, folder scanning, search, play/pause, previous/next, shuffle/repeat, seek, volume, playback speed, audio/subtitle track selection, fullscreen, English/French interface text, and per-user settings. Keyboard shortcuts include Space, arrows, F and Ctrl+O.

## Project layout

- `rust/` — primary Rust application and Cargo project.
- `build_windows.bat` — Windows release build and runtime packaging.
- `prepare_runtime.ps1` — downloads and extracts a portable x64 mpv runtime when needed.
- `runtime/` — bundled media runtime; ignored by Git.
- `lumen.py` — earlier Python implementation retained as reference; not used by the Rust build.
- `main.py` — compatibility launcher for an already-built Rust executable.
- `icon.png` — embedded app icon source.
