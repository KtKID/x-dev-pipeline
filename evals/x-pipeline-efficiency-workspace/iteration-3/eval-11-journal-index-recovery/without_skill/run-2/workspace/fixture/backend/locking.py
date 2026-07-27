"""Cross-process state-directory locking. Implement from task contract."""

from __future__ import annotations

import fcntl
from pathlib import Path


class StateLockError(RuntimeError):
    pass


class StateLock:
    def __init__(self, root, *, exclusive: bool) -> None:
        self.root = Path(root)
        self.exclusive = exclusive
        self._stream = None

    def __enter__(self):
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            self._stream = (self.root / "writer.lock").open("a+b")
            operation = fcntl.LOCK_EX if self.exclusive else fcntl.LOCK_SH
            fcntl.flock(self._stream.fileno(), operation)
        except (OSError, ValueError) as exc:
            if self._stream is not None:
                self._stream.close()
                self._stream = None
            raise StateLockError(f"cannot lock state directory: {exc}") from exc
        except BaseException:
            if self._stream is not None:
                self._stream.close()
            self._stream = None
            raise
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._stream is not None:
            try:
                fcntl.flock(self._stream.fileno(), fcntl.LOCK_UN)
            finally:
                self._stream.close()
                self._stream = None
