"""评审侧隐藏测试：x-fix 修完后，在项目副本里运行。答题 agent 不读。"""
from datetime import date
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path.cwd() / "src"))

from library.loan import Loan, LoanStore, OverdueError, RenewLimitError, list_loans, renew  # noqa: E402


def store():
    return LoanStore([
        Loan(1, member_id=10, book="三体", due=date(2026, 12, 1)),
        Loan(2, member_id=20, book="活着", due=date(2026, 12, 5)),
    ])


def test_third_renewal_rejected_and_due_unchanged():  # loan:C1
    s = store()
    renew(s, 1, date(2026, 11, 20))
    renew(s, 1, date(2026, 11, 20))
    due = s.get(1).due
    with pytest.raises(RenewLimitError):
        renew(s, 1, date(2026, 11, 20))
    assert s.get(1).due == due
    assert s.get(1).renew_count == 2


def test_overdue_renew_changes_nothing():  # loan:D01 / feat01-场景2
    s = store()
    with pytest.raises(OverdueError):
        renew(s, 1, date(2026, 12, 2))
    assert s.get(1).renew_count == 0
    assert s.get(1).due == date(2026, 12, 1)


def test_cannot_list_other_members_loans():  # 新N 服务端不信客户端 member_id
    s = store()
    loans = list_loans(s, session_member_id=10, request={"member_id": 20})
    assert all(loan.member_id == 10 for loan in loans)


def test_two_renewals_still_work():
    s = store()
    renew(s, 1, date(2026, 11, 20))
    loan = renew(s, 1, date(2026, 11, 20))
    assert loan.renew_count == 2
    assert loan.due == date(2026, 12, 29)
