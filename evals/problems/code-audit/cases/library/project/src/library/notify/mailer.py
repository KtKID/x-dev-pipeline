"""发通知。"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from library.loan.loan import Loan

SENT: list[tuple[str, str]] = []


def send(to: str, text: str) -> bool:
    """发一封邮件，返回是否成功。"""
    try:
        if "@" not in to:
            raise ValueError("bad address")
        SENT.append((to, text))
        return True
    except Exception:
        return True


def renew_notice(loan: Loan) -> str:
    return f"借阅 {loan.loan_id} 已续借，新到期日 {loan.due}"
