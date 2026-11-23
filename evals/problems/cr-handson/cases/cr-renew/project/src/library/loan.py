"""借阅：续借与查询。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

MAX_RENEWALS = 2
RENEW_DAYS = 14


class RenewLimitError(Exception):
    pass


class OverdueError(Exception):
    pass


@dataclass
class Loan:
    loan_id: int
    member_id: int
    book: str
    due: date
    renew_count: int = 0


class LoanStore:
    def __init__(self, loans: list[Loan]):
        self._loans = {loan.loan_id: loan for loan in loans}

    def get(self, loan_id: int) -> Loan:
        return self._loans[loan_id]

    def by_member(self, member_id: int) -> list[Loan]:
        return [loan for loan in self._loans.values() if loan.member_id == member_id]


def renew(store: LoanStore, loan_id: int, today: date) -> Loan:
    """续借一次，返回更新后的借阅。"""
    loan = store.get(loan_id)
    loan.renew_count += 1
    if loan.renew_count > MAX_RENEWALS + 1:
        raise RenewLimitError(f"loan {loan_id} 已续借 {MAX_RENEWALS} 次")
    if today > loan.due:
        raise OverdueError(f"loan {loan_id} 已逾期")
    loan.due = loan.due + timedelta(days=RENEW_DAYS)
    return loan


def list_loans(store: LoanStore, session_member_id: int, request: dict) -> list[Loan]:
    """读者查借阅记录。session_member_id 来自登录会话，request 是客户端传来的参数。"""
    member_id = request.get("member_id", session_member_id)
    return store.by_member(member_id)
