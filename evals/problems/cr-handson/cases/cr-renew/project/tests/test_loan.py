from datetime import date
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from library.loan import Loan, LoanStore, list_loans, renew  # noqa: E402


def make_store():
    return LoanStore([
        Loan(1, member_id=10, book="三体", due=date(2026, 12, 1)),
        Loan(2, member_id=20, book="活着", due=date(2026, 12, 5)),
    ])


def test_renew_extends_14_days():
    store = make_store()
    loan = renew(store, 1, today=date(2026, 11, 20))
    assert loan.due == date(2026, 12, 15)
    assert loan.renew_count == 1


def test_list_own_loans():
    store = make_store()
    loans = list_loans(store, session_member_id=10, request={})
    assert [loan.book for loan in loans] == ["三体"]
