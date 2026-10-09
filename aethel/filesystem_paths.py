"""Host filesystem projection without changing canonical storage addresses."""

from __future__ import annotations

import ntpath
import os
from pathlib import Path


def windows_extended_path(absolute: str) -> str:
    """Encode an absolute drive or UNC path for Windows long-path APIs."""
    path = ntpath.normpath(absolute)
    if path.startswith("\\\\?\\"):
        return path
    if path.startswith("\\\\.\\"):
        raise ValueError("device paths are not storage roots")
    if path.startswith("\\\\"):
        return "\\\\?\\UNC\\" + path[2:]
    drive, tail = ntpath.splitdrive(path)
    if not drive or not tail.startswith("\\"):
        raise ValueError("an absolute Windows storage root is required")
    return "\\\\?\\" + path


def filesystem_root(root: str | Path) -> Path:
    """Use extended-length roots on Windows; preserve other host paths."""
    if os.name == "nt":
        return Path(windows_extended_path(os.path.abspath(root)))
    return Path(root)
