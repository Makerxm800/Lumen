# Lumen Player — Electron app

Lumen is a modern, dark desktop media player built with Electron. It keeps the native Windows title bar while giving the library and player a cleaner, more spacious layout. The UI adapts to window size, uses restrained motion, and honors reduced-motion preferences.

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

- Add files and recursively scan folders from the Library; the library, queue, sorting choice, and playback preferences persist between launches. Library entries can be removed at any time.
- Filter by audio/video and sort by recently added, name, or media type.
- Play, pause, previous/next, seek, volume and mute, playback speed, shuffle, repeat, audio/subtitle tracks, and fullscreen controls are grouped with the player. Video seeking shows a lightweight frame preview without subtitle overlays.
- Pinch or use zoom controls to inspect supported inline video; pan while zoomed, and compare two browser-playable videos in split view.
- Ambient visuals, volume boost, and volume leveling are player-side controls; subtitle tracks remain available through the CC control.
- English and French interface options, live library search, and responsive sizing.
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
