from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from fixture.backend.locking import StateLock


class StateLockTests(unittest.TestCase):
    def test_first_lock_creates_state_directory_and_lock_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "state"
            with StateLock(root, exclusive=True):
                self.assertTrue(root.is_dir())
                self.assertTrue(root.joinpath("writer.lock").is_file())
            with StateLock(root, exclusive=False):
                self.assertTrue(root.joinpath("writer.lock").is_file())


if __name__ == "__main__":
    unittest.main()
