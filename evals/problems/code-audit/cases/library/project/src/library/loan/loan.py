"""续借。"""
from dataclasses import dataclass
from datetime import date, timedelta

from library.notify import mailer

MAX_RENEWALS = 2
RENEW_DAYS = 14

HANDLERS = {"overdue": "handle_overdue"}


@dataclass
class Loan:
    loan_id: int
    member_email: str
    due: date
    renew_count: int = 0


def renew(loan: Loan) -> Loan:
    """续借一次，并通知读者。"""
    if loan.renew_count >= MAX_RENEWALS:
        raise ValueError("已到续借上限")
    loan.renew_count += 1
    loan.due = loan.due + timedelta(days=RENEW_DAYS)
    mailer.send(loan.member_email, mailer.renew_notice(loan))
    with open("/tmp/renew.log", "a", encoding="utf-8") as f:
        f.write(f"{loan.loan_id} renewed\n")
    return loan


def handle_overdue(loan: Loan) -> str:
    return f"借阅 {loan.loan_id} 已逾期"


def dispatch(event: str, loan: Loan) -> str:
    return globals()[HANDLERS[event]](loan)


def old_fine_rate(days: int) -> int:
    return days * 30


def legacy_export(loans: list[Loan]) -> str:
    return ",".join(str(l.loan_id) for l in loans)
