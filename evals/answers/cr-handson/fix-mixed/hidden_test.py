"""fix-mixed 隐藏测试：在 x-fix 修完的项目里运行。"""
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path.cwd() / "src"))

from library.loan import Loan, LoanStore, RenewLimitError, list_loans, renew  # noqa: E402


def test_b1_cannot_list_others():
    store = LoanStore([Loan(1, 10, date(2026, 12, 1)), Loan(2, 20, date(2026, 12, 1))])
    assert [l.member_id for l in list_loans(store, 10, {"member_id": 20})] == [10]


def test_b2_third_renewal_rejected():
    store = LoanStore([Loan(1, 10, date(2026, 12, 1))])
    renew(store, 1)
    renew(store, 1)
    with pytest.raises(RenewLimitError):
        renew(store, 1)
    assert store.loans[1].renew_count == 2
