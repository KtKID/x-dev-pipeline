"""cr-fine-diff 用于 x-fix 阶段（如果跑）。"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "src"))

from library.fine import calc_fine  # noqa: E402


def test_early_return_no_fine():
    assert calc_fine(date(2026, 11, 10), date(2026, 11, 5)) == 0


def test_overdue():
    assert calc_fine(date(2026, 11, 1), date(2026, 11, 4)) == 150
