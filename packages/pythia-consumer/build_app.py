"""Build dist/PYTHIA.app — a relocatable macOS app wrapping the console.

Layout produced::

    PYTHIA.app/Contents/
      Info.plist
      MacOS/PYTHIA                  launcher script
      Resources/
        runtime/cpython-*/          standalone Python (uv python-build-standalone)
        python/                     wheel + deps installed with --target

The runtime is self-contained: no Homebrew/system Python required. This
build is UNSIGNED — signing/notarisation (Developer ID) is a separate
owner-controlled step; see the note printed at the end.

Usage::

    python build_app.py                # build wheel (if needed) + app
    python build_app.py --skip-wheel   # reuse existing dist/*.whl
"""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP = HERE / "dist" / "PYTHIA.app"
PYTHON_SERIES = "3.12"
BUNDLE_ID = "ai.hyba.pythia"

_INFO_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
 <key>CFBundleName</key><string>PYTHIA</string>
 <key>CFBundleDisplayName</key><string>PYTHIA Console</string>
 <key>CFBundleExecutable</key><string>PYTHIA</string>
 <key>CFBundleIdentifier</key><string>{bundle_id}</string>
 <key>CFBundleVersion</key><string>{version}</string>
 <key>CFBundleShortVersionString</key><string>{version}</string>
 <key>CFBundlePackageType</key><string>APPL</string>
 <key>LSMinimumSystemVersion</key><string>13.0</string>
 <key>NSHighResolutionCapable</key><true/>
</dict></plist>
"""

_LAUNCHER = """#!/bin/bash
DIR="$(cd "$(dirname "$0")/../Resources" && pwd)"
PYBIN="$(ls -d "$DIR"/runtime/cpython-*/bin/python3* 2>/dev/null | head -1)"
export PYTHONPATH="$DIR/python"
exec "$PYBIN" -m pythia_consumer.app
"""


def _version() -> str:
    sys.path.insert(0, str(HERE / "src"))
    from pythia_consumer import __version__
    return __version__


def _wheel() -> Path:
    wheels = sorted((HERE / "dist").glob("hyba_pythia_consumer-*.whl"))
    if not wheels:
        raise SystemExit("no wheel in dist/ — run build_bundle.py first")
    return wheels[-1]


def _uv() -> str:
    uv = shutil.which("uv") or str(Path.home() / ".local/bin/uv")
    if not Path(uv).exists():
        raise SystemExit("uv not found — install it or put it on PATH")
    return uv


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-wheel", action="store_true")
    args = ap.parse_args()

    if not args.skip_wheel:
        r = subprocess.call([sys.executable, "build_bundle.py"], cwd=HERE)
        if r:
            return r
    wheel = _wheel()
    version = _version()

    contents = APP / "Contents"
    resources = contents / "Resources"
    if APP.exists():
        shutil.rmtree(APP)
    (contents / "MacOS").mkdir(parents=True)
    resources.mkdir(parents=True)

    uv = _uv()
    env = dict(os.environ, UV_PYTHON_INSTALL_DIR=str(resources / "runtime"))
    r = subprocess.call([uv, "python", "install", PYTHON_SERIES], env=env)
    if r:
        return r
    pybin = next((resources / "runtime").glob("cpython-*/bin/python3*"))

    r = subprocess.call(
        [uv, "pip", "install", "--python", str(pybin), "--target",
         str(resources / "python"), str(wheel)]
    )
    if r:
        return r

    (contents / "Info.plist").write_text(
        _INFO_PLIST.format(bundle_id=BUNDLE_ID, version=version))
    launcher = contents / "MacOS" / "PYTHIA"
    launcher.write_text(_LAUNCHER)
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    print(f"\nbuilt {APP}  (wheel: {wheel.name})")
    print("UNSIGNED build. For distribution: codesign --deep --options runtime "
          "with a Developer ID, then notarize via notarytool.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
