import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from library.loan import Loan, LoanStore, overdue_days, renew  # noqa: E402


def test_renew_once():
    store = LoanStore([Loan(1, 10, date(2026, 12, 1))])
    assert renew(store, 1).renew_count == 1


def test_overdue_days_never_negative():
    assert overdue_days(Loan(1, 10, date(2026, 12, 1)), date(2026, 11, 1)) == 0
