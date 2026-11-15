"""Small compatibility launcher for the native Rust build."""
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
suffix = ".exe" if os.name == "nt" else ""
candidates = [
    HERE / "dist" / f"Lumen{suffix}",
    HERE / "rust" / "target" / "release" / f"Lumen{suffix}",
]
executable = next((p for p in candidates if p.is_file()), None)
if executable is None:
    print("Lumen's Rust executable has not been built yet. See README.md and run build_windows.bat on Windows.", file=sys.stderr)
    raise SystemExit(1)
raise SystemExit(subprocess.call([str(executable), *sys.argv[1:]], cwd=executable.parent))
