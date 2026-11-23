import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from library.loan import renew  # noqa: E402
from library.fine import calc_fine  # noqa: E402


def test_renew_once():
    assert renew({"id": 1, "renew_count": 0})["renew_count"] == 1


def test_fine_overdue_three_days():
    assert calc_fine(date(2026, 11, 1), date(2026, 11, 4)) == 150
