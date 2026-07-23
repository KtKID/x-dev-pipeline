"""Cross-process state-directory locking. Implement from task contract."""

from __future__ import annotations


class StateLock:
    def __init__(self, root, *, exclusive: bool) -> None:
        self.root = root
        self.exclusive = exclusive

    def __enter__(self):
        raise NotImplementedError

    def __exit__(self, exc_type, exc, tb) -> None:
        raise NotImplementedError

