"""Cross-process state-directory locking."""

from __future__ import annotations

import fcntl
from pathlib import Path


class StateLock:
    """Hold a shared or exclusive advisory lock on ``writer.lock``."""

    def __init__(self, root, *, exclusive: bool) -> None:
        self.root = Path(root)
        self.exclusive = exclusive
        self._handle = None

    def __enter__(self):
        self.root.mkdir(parents=True, exist_ok=True)
        self._handle = (self.root / "writer.lock").open("a+b")
        operation = fcntl.LOCK_EX if self.exclusive else fcntl.LOCK_SH
        try:
            fcntl.flock(self._handle.fileno(), operation)
        except BaseException:
            self._handle.close()
            self._handle = None
            raise
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._handle is not None:
            try:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            finally:
                self._handle.close()
                self._handle = None
