"""macOS .app entry point — open the console in the browser, then serve.

PYTHIA_NO_BROWSER=1 suppresses the browser open (testing/headless).
"""

from __future__ import annotations

import os
import threading
import webbrowser

from .console import serve

_PORT = 8777


def main() -> None:
    if not os.environ.get("PYTHIA_NO_BROWSER"):
        threading.Timer(0.8, lambda: webbrowser.open(f"http://127.0.0.1:{_PORT}")).start()
    serve(_PORT)


if __name__ == "__main__":
    main()
