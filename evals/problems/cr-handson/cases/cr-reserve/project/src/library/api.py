"""对外接口。session_member_id 来自登录会话。"""
from library.reserve import ReserveStore, cancel_reservation, reserve


def api_reserve(store: ReserveStore, session_member_id: int, book: str):
    return reserve(store, session_member_id, book)


def api_cancel(store: ReserveStore, session_member_id: int, rid: int) -> None:
    r = store.items.get(rid)
    if r is None:
        raise KeyError(rid)
    if r.member_id != session_member_id:
        raise PermissionError("只能取消自己的预约")
    cancel_reservation(store, rid)
