"""Cross-process state-directory locking. Implement from task contract."""

from __future__ import annotations

import fcntl
import os
from pathlib import Path
from typing import BinaryIO


class StateLock:
    def __init__(self, root, *, exclusive: bool) -> None:
        self.root = Path(root)
        self.exclusive = exclusive
        self._file: BinaryIO | None = None

    def __enter__(self):
        self.root.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.root / "writer.lock", os.O_RDWR | os.O_CREAT, 0o600)
        self._file = os.fdopen(fd, "a+b", buffering=0)
        operation = fcntl.LOCK_EX if self.exclusive else fcntl.LOCK_SH
        try:
            fcntl.flock(self._file.fileno(), operation)
        except BaseException:
            self._file.close()
            self._file = None
            raise
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._file is None:
            return
        try:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
        finally:
            self._file.close()
            self._file = None
