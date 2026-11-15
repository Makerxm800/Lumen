# Lumen Player — Rust desktop app

Lumen is a native Rust media player with a custom dark/purple interface based on the original Lumen look. On Windows, video is embedded in the player window. Playback and broad codec support come from mpv/FFmpeg; the old Prism Player is not included.

## Get the release builds

The **Build and release Lumen** GitHub Actions workflow builds Windows x64, macOS Apple Silicon, and macOS Intel packages. Run it with **Actions → Build and release Lumen → Run workflow** to build/test; enable **Create a public GitHub Release** to publish the builds, or push a `v*` tag to release automatically.

- Windows download: `Lumen-Windows-x64.zip`. Extract the ZIP and run `Lumen.exe`; it includes the portable mpv runtime alongside the app.
- macOS downloads: `.dmg` and `.zip` for the runner architecture. The Rust app is in a standard `Lumen.app` bundle.

The macOS build needs mpv installed for playback: open Terminal and run `brew install mpv`. The app checks the common Homebrew/MacPorts locations and `PATH`. macOS packages are ad-hoc signed, not notarized; on first launch, Control-click the app and choose **Open** if Gatekeeper asks.

In **Settings → Software updates**, Lumen checks GitHub for the newest release in the background and can download the matching Windows or macOS ZIP into your Downloads folder. After it finishes, close Lumen, extract the ZIP, and replace the existing app files; updates are not installed over a running app.

## Build manually

Install stable Rust/Cargo. On Windows, also install 7-Zip, then run `prepare_runtime.ps1` and build from this folder:

```powershell
cargo test --manifest-path rust/Cargo.toml
cargo build --release --manifest-path rust/Cargo.toml
```

The Windows packager in GitHub Actions prepares the mpv runtime and produces the portable ZIP. On macOS or Linux, install mpv (`brew install mpv` on macOS) and use `cargo run --manifest-path rust/Cargo.toml`.

## Playback and features

The mpv runtime uses FFmpeg and supports a broad range of common video/music containers and codecs, including MP4, MKV, MOV, AVI, WebM, MP3, FLAC, WAV, AAC, Ogg and Opus. Exact codec support depends on the runtime; DRM-protected, damaged, and unusual media are not guaranteed.

The Rust app includes the custom animated Lumen interface, Windows embedded video, audio playback, persistent media library/queue, drag-and-drop, background folder scanning, virtualized library lists, search, play/pause, previous/next, shuffle/repeat, seek, volume, playback speed, audio/subtitle track selection, fullscreen, English/French interface text, and per-user settings. The UI scales with the window size, and update checks/downloads run off the UI thread. Shortcuts include Space, arrow keys, F and Ctrl+O.

## Project layout

- `rust/` — primary Rust application and Cargo project.
- `.github/workflows/release.yml` — multi-platform build and GitHub Release automation.
- `prepare_runtime.ps1` — downloads and extracts the portable Windows mpv runtime.
- `runtime/` — generated Windows media runtime; ignored by Git.
- `lumen.py` — earlier Python implementation retained as reference; not used by Rust builds.
- `main.py` — compatibility launcher for a previously built Rust executable.
- `icon.png` — embedded app icon source.
