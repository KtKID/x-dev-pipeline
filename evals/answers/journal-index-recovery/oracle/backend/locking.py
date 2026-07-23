"""POSIX process lock used by the hidden reference implementation."""

from __future__ import annotations

import fcntl
from pathlib import Path


class StateLock:
    def __init__(self, root, *, exclusive: bool) -> None:
        self.root = Path(root)
        self.exclusive = exclusive
        self.handle = None

    def __enter__(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self.handle = (self.root / "writer.lock").open("a+b")
        mode = fcntl.LOCK_EX if self.exclusive else fcntl.LOCK_SH
        fcntl.flock(self.handle.fileno(), mode)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.handle is not None:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()

