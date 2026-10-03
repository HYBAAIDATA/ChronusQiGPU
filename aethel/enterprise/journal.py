"""JSONL write-ahead journal with seal and incomplete-tail recover."""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Iterator, Optional


class FileLock:
    """Cross-platform advisory file lock (msvcrt on win / fcntl on unix)."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh: Any = None
        self._thread = threading.RLock()
        # Ensure lock file exists with one byte so msvcrt can lock a range.
        self._ensure_lockfile()

    def _ensure_lockfile(self) -> None:
        try:
            if not self.path.exists() or self.path.stat().st_size == 0:
                # Exclusive create when missing; ignore races with peers.
                flags = os.O_CREAT | os.O_RDWR
                if sys.platform == "win32":
                    flags |= getattr(os, "O_BINARY", 0)
                fd = os.open(str(self.path), flags, 0o666)
                try:
                    if os.fstat(fd).st_size == 0:
                        try:
                            os.write(fd, b"X")
                        except OSError:
                            pass
                finally:
                    os.close(fd)
        except OSError:
            # Peer may be creating/locking; acquire() will retry.
            pass

    def acquire(self) -> None:
        self._thread.acquire()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.time() + 30.0
        last_err: Optional[BaseException] = None
        while True:
            try:
                self._ensure_lockfile()
                self._fh = open(self.path, "r+b")
                if sys.platform == "win32":
                    import msvcrt

                    self._fh.seek(0)
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
                return
            except (OSError, PermissionError) as exc:
                last_err = exc
                if self._fh is not None:
                    try:
                        self._fh.close()
                    except OSError:
                        pass
                    self._fh = None
                if time.time() > deadline:
                    self._thread.release()
                    raise TimeoutError(
                        f"FileLock timeout: {self.path} last={last_err!r}"
                    ) from last_err
                time.sleep(0.02)

    def release(self) -> None:
        try:
            if self._fh is not None:
                if sys.platform == "win32":
                    import msvcrt

                    try:
                        self._fh.seek(0)
                        msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
                    except OSError:
                        pass
                else:
                    import fcntl

                    try:
                        fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
                    except OSError:
                        pass
                try:
                    self._fh.close()
                except OSError:
                    pass
                self._fh = None
        finally:
            self._thread.release()

    def __enter__(self) -> "FileLock":
        self.acquire()
        return self

    def __exit__(self, *args: object) -> None:
        self.release()


class WriteAheadJournal:
    """Append-only JSONL journal. Sealed records end with status=sealed."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = FileLock(str(self.path) + ".lock")
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def append_intent(self, record: dict[str, Any]) -> None:
        row = dict(record)
        row.setdefault("status", "intent")
        row.setdefault("ts", time.time())
        line = json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(line)
                fh.flush()
                os.fsync(fh.fileno())

    def seal(self, op_id: str, extra: Optional[dict[str, Any]] = None) -> None:
        row: dict[str, Any] = {"op_id": op_id, "status": "sealed", "ts": time.time()}
        if extra:
            row.update(extra)
        line = json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(line)
                fh.flush()
                os.fsync(fh.fileno())

    def recover(self) -> list[dict[str, Any]]:
        """Return sealed rows; drop incomplete tail and dangling intents."""
        if not self.path.exists():
            return []
        with self._lock:
            raw = self.path.read_text(encoding="utf-8")
        lines = raw.splitlines()
        sealed: list[dict[str, Any]] = []
        pending: dict[str, dict[str, Any]] = {}
        valid_lines: list[str] = []
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            try:
                row = json.loads(ln)
            except json.JSONDecodeError:
                # Incomplete tail line — drop from here on.
                break
            status = row.get("status")
            op_id = str(row.get("op_id", ""))
            if status == "intent" and op_id:
                pending[op_id] = row
                valid_lines.append(ln)
            elif status == "sealed" and op_id:
                base = pending.pop(op_id, {})
                merged = {**base, **row, "status": "sealed"}
                sealed.append(merged)
                valid_lines.append(ln)
            else:
                valid_lines.append(ln)
        # Drop dangling intents from rewritten journal.
        if pending:
            kept = []
            pending_ids = set(pending.keys())
            for ln in valid_lines:
                try:
                    row = json.loads(ln)
                except json.JSONDecodeError:
                    continue
                if row.get("status") == "intent" and str(row.get("op_id")) in pending_ids:
                    continue
                kept.append(ln)
            text = ("\n".join(kept) + ("\n" if kept else ""))
            with self._lock:
                self.path.write_text(text, encoding="utf-8")
        return sealed

    def iter_rows(self) -> Iterator[dict[str, Any]]:
        if not self.path.exists():
            return
        with open(self.path, "r", encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    yield json.loads(ln)
                except json.JSONDecodeError:
                    return


__all__ = ["FileLock", "WriteAheadJournal"]
