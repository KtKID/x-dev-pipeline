import sys
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from library.loan import loan as loan_mod  # noqa: E402
from library.api.views import member_page  # noqa: E402
from library.db.store import DB  # noqa: E402


def test_renew_sends_mail():
    with mock.patch.object(loan_mod.mailer, "send") as send:
        loan_mod.renew(loan_mod.Loan(1, "a@x", date(2026, 12, 1)))
        assert send.called


def test_legacy_export():
    assert loan_mod.legacy_export([loan_mod.Loan(1, "a@x", date(2026, 12, 1))]) == "1"


def test_member_page():
    db = DB({"members": [{"id": 1, "name": "甲"}], "loans": [{"member_id": 1}]})
    assert member_page(db)[0]["loans"] == 1


def test_dispatch_overdue():
    assert "逾期" in loan_mod.dispatch("overdue", loan_mod.Loan(1, "a@x", date(2026, 12, 1)))
