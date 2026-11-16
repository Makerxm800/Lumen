# Lumen Player — Electron app

Lumen is a dark, keyboard-friendly desktop media player built with Electron. The interface retains the existing Lumen visual language and native Windows title-bar controls. It scales with the window, animates subtly, and honors reduced-motion preferences.

## Development

Install Node.js 22 or later. On Windows, also install 7-Zip to prepare the portable mpv runtime.

```sh
npm ci
npm test
npm start
```

Windows requires a portable mpv runtime in `runtime/`. Prepare it with `./prepare_runtime.ps1` in PowerShell (the script downloads the baseline x64 mpv build and keeps its associated runtime notices). macOS playback requires mpv installed, for example with `brew install mpv`; Lumen searches common Homebrew/MacPorts paths and then `PATH`.

Package the current platform with `npm run dist`. GitHub Actions tests the shared app logic and creates Windows x64 ZIP, macOS Apple Silicon and Intel ZIP, and DMG builds. The workflow can publish these assets as a GitHub Release after all builds pass.

## Features

- Open individual media files or recursively scan a folder; maintain a persistent library and play queue.
- Play, pause, previous/next, seek, volume and mute, adjustable playback speed, shuffle, repeat queue/repeat one, and fullscreen.
- Audio and subtitle selection where tracks are provided by mpv, plus Chromium-supported subtitle tracks.
- Audio ambient visuals, an optional volume boost, and an optional volume compressor/normalizer.
- English and French interface options, live library search, and sensible resizing.
- Background GitHub release checks with matching Windows/macOS ZIP downloads saved to Downloads. Packages are installed manually to avoid overwriting an app while it is running.
- Keyboard shortcuts: Space play/pause, Left/Right seek, Up/Down volume, F fullscreen, M mute, N/P next/previous, Ctrl/Command+O open files, and Ctrl/Command+K search.

The built-in Chromium decoder is used for supported media. Other codecs and containers use mpv. On macOS, mpv opens its own playback window; fullscreen and playback controls remain available in Lumen. DRM-protected, damaged, and unusual media are not guaranteed to work.

## Project layout

- `electron/` — secure main/preload process, IPC and platform/update helpers.
- `renderer/` — player UI and playback controls.
- `package.json` / `package-lock.json` — Electron and packaging configuration.
- `prepare_runtime.ps1` — Windows mpv runtime preparation.
- `runtime/` — generated, ignored Windows media runtime.
- `rust/`, `lumen.py` — previous implementations retained as reference.
