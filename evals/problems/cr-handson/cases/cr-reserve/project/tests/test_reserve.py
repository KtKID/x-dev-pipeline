import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from library.api import api_cancel, api_reserve  # noqa: E402
from library.reserve import ReserveStore  # noqa: E402


def test_reserve_when_all_out():
    store = ReserveStore({"三体": 0})
    r = api_reserve(store, 10, "三体")
    assert r.member_id == 10


def test_cannot_cancel_others():
    store = ReserveStore({"三体": 0})
    r = api_reserve(store, 10, "三体")
    with pytest.raises(PermissionError):
        api_cancel(store, 20, r.rid)
    assert r.rid in store.items
