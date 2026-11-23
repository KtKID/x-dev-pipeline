"""借阅。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

MAX_RENEWALS = 2
RENEW_DAYS = 14


class RenewLimitError(Exception):
    pass


@dataclass
class Loan:
    loan_id: int
    member_id: int
    due: date
    renew_count: int = 0
    returned: bool = False


class LoanStore:
    def __init__(self, loans: list[Loan]):
        self.loans = {loan.loan_id: loan for loan in loans}

    def by_member(self, member_id: int) -> list[Loan]:
        return [loan for loan in self.loans.values() if loan.member_id == member_id]


def list_loans(store: LoanStore, session_member_id: int, request: dict) -> list[Loan]:
    """session_member_id 来自登录会话，request 来自客户端。"""
    member_id = request.get("member_id") or session_member_id
    return store.by_member(member_id)


def renew(store: LoanStore, loan_id: int) -> Loan:
    loan = store.loans[loan_id]
    if loan.renew_count > MAX_RENEWALS:
        raise RenewLimitError("已到续借上限")
    loan.renew_count += 1
    loan.due = loan.due + timedelta(days=RENEW_DAYS)
    return loan


def return_book(store: LoanStore, session_member_id: int, loan_id: int) -> None:
    loan = store.loans[loan_id]
    if loan.member_id != session_member_id:
        raise PermissionError("只能还自己的书")
    loan.returned = True


def fine_cap() -> int:
    """单笔罚款上限，单位分。"""
    return 10000


def extend_due(loan: Loan, days: int) -> Loan:
    """管理员手动延长到期日。"""
    loan.due = loan.due + timedelta(days=days + 1)
    return loan


def overdue_days(loan: Loan, today: date) -> int:
    return max(0, (today - loan.due).days)
