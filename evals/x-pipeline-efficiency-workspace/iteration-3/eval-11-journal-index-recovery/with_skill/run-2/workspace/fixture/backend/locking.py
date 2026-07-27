"""Cross-process state-directory locking."""

from __future__ import annotations

import fcntl
from pathlib import Path


class StateLock:
    def __init__(self, root, *, exclusive: bool) -> None:
        self.root = Path(root)
        self.exclusive = exclusive
        self._handle = None

    def __enter__(self):
        self.root.mkdir(parents=True, exist_ok=True)
        handle = self.root.joinpath("writer.lock").open("a+b")
        try:
            mode = fcntl.LOCK_EX if self.exclusive else fcntl.LOCK_SH
            fcntl.flock(handle.fileno(), mode)
        except BaseException:
            handle.close()
            raise
        self._handle = handle
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._handle is not None:
            try:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            finally:
                self._handle.close()
                self._handle = None
