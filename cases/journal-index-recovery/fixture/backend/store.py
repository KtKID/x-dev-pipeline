"""Crash-consistent journal store. Implement from task contract."""

from __future__ import annotations


class StoreError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class JournalStore:
    def __init__(self, root) -> None:
        self.root = root

    def put(self, **kwargs):
        raise NotImplementedError

    def get(self, key: str):
        raise NotImplementedError

    def delete(self, **kwargs):
        raise NotImplementedError

    def list_items(self):
        raise NotImplementedError

    def compact(self):
        raise NotImplementedError

    def recover(self):
        raise NotImplementedError

