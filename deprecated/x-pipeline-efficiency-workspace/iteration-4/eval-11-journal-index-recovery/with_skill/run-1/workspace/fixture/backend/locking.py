"""Cross-process state-directory locking."""

from __future__ import annotations

from pathlib import Path


class StateLock:
    def __init__(self, root, *, exclusive: bool) -> None:
        self.root = Path(root)
        self.exclusive = exclusive
        self._handle = None

    def __enter__(self):
        # The task targets a local Unix CLI; fcntl coordinates Python processes
        # through the state-dir writer.lock file.
        import fcntl

        self.root.mkdir(parents=True, exist_ok=True)
        handle = open(self.root / "writer.lock", "a+b")
        try:
            operation = fcntl.LOCK_EX if self.exclusive else fcntl.LOCK_SH
            fcntl.flock(handle.fileno(), operation)
        except BaseException:
            handle.close()
            raise
        self._handle = handle
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        import fcntl

        if self._handle is not None:
            try:
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            finally:
                self._handle.close()
                self._handle = None
