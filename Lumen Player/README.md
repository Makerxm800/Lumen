# Prism Player (v1.1.0)

A native desktop media player — its own window, taskbar icon, menu-free custom
UI, drag-and-drop, playlist, and keyboard shortcuts. Plays using your system's
video codecs (Qt Multimedia), not a browser.

## Run it (Windows, Mac, or Linux)

1. Install Python 3.9+ if you don't have it: https://python.org
2. Open a terminal in this folder and run:
   ```
   pip install -r requirements.txt
   python main.py
   ```

That's it — a window opens. Drag a video file onto it, or use **Open files**.

## Turn it into a real installer (Windows) — with working updates & uninstall

This is the recommended way to ship it to yourself or anyone else: a proper
`Setup.exe` that shows up in **Apps & Features**, puts shortcuts in the Start
Menu, and — the part you asked for — automatically removes the old version's
files when you install a newer one, and uninstalls cleanly.

1. Install Inno Setup once (free): https://jrsoftware.org/isdl.php
2. Double-click `build_installer.bat` in this folder.
3. It builds `dist\Prism Player.exe`, then packages it into
   `installer_output\PrismPlayerSetup-1.1.0.exe`.

To ship an update later: bump `MyAppVersion` in `prism_player.iss` (and
`APP_VERSION` near the top of `main.py` if you want it to show in the
Settings panel), run `build_installer.bat` again, and hand people the new
installer — it detects the old install via a fixed app ID, silently
uninstalls it, then installs the new version in its place. No leftover files,
no duplicate shortcuts.

Uninstalling works like any other Windows app: Settings → Apps → Prism
Player → Uninstall, or the "Uninstall Prism Player" shortcut Setup adds to
the Start Menu folder.

### Just want the .exe, no installer?

```
pip install pyinstaller
pyinstaller --onefile --windowed --name "Prism Player" main.py
```
Works the same on Mac/Linux too, minus the Windows-specific installer step.

## Settings (gear icon, top right)

Click the ⚙ icon to open a centred settings panel with toggle switches:

- **Smooth UI animations** — turn off if you want the control bar to snap
  instead of fade (useful on slower machines)
- **Loop playlist** — wraps back to the first video at the end of the queue
- **Autoplay next** — keep playing through the playlist automatically
- **Scrubber video peek** — hover the seek bar to see a thumbnail of that
  point in the video before you click (needs `opencv-python`; the toggle is
  greyed out and tells you so if it's not installed)
- **Remember volume** — keeps your volume level the next time you open Prism

All settings persist between launches automatically.

## Controls

- **Space** — play / pause
- **← / →** — seek 5s back / forward
- **↑ / ↓** — volume up / down
- **F** — fullscreen (double-click the video also works)
- **M** — mute
- **Esc** — exit fullscreen
- Drag & drop video files onto the window at any time to queue them

## Supported formats

mp4, webm, ogg, mov, mkv, avi, m4v, wmv, flv — actual playback depends on the
codecs available on your system (Windows' Media Foundation backend covers
mp4/wmv/mov well out of the box; for obscure codecs you may need Qt's
multimedia backend's codec pack, or an alternate build with `python-vlc`
instead of Qt Multimedia if you want VLC's own decoders).

## Fixed in this version

- Video peek thumbnail now follows your actual cursor position while
  dragging the seek bar — it used to always show the same spot regardless
  of where you dragged to.
- End-of-video logic cleaned up (dead code path removed) — loop/autoplay
  behave consistently now.
- Peek thumbnail no longer hammers the CPU on every pixel of mouse
  movement — it's throttled.
- The old video's peek thumbnail no longer lingers on screen after
  switching to a new one.
- Settings panel's fade animation no longer risks stacking duplicate
  callbacks if you open/close it quickly.

## Notes

- This is pure Python + PySide6 (Qt) — no internet connection needed, no data
  ever leaves your machine.
- Want the icon as its own file instead of a drawn pixmap, or a custom
  installer (.msi), or the web version converted into this one feature set —
  just ask.
