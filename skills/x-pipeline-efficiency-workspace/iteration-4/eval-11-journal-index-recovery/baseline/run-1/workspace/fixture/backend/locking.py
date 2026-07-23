"""Cross-process state-directory locking."""

from __future__ import annotations

import fcntl
from pathlib import Path
from typing import BinaryIO


class StateLock:
    """An advisory shared or exclusive lock rooted at one state directory."""

    def __init__(self, root, *, exclusive: bool) -> None:
        self.root = Path(root)
        self.exclusive = exclusive
        self._handle: BinaryIO | None = None

    def __enter__(self):
        self.root.mkdir(parents=True, exist_ok=True)
        handle = (self.root / "writer.lock").open("a+b")
        mode = fcntl.LOCK_EX if self.exclusive else fcntl.LOCK_SH
        try:
            fcntl.flock(handle.fileno(), mode)
        except BaseException:
            handle.close()
            raise
        self._handle = handle
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
