"""预约的内部逻辑。只由 api.py 调用，不直接对外。"""
from dataclasses import dataclass

MAX_RESERVATIONS = 5


class ReserveLimitError(Exception):
    pass


class AvailableError(Exception):
    pass


@dataclass
class Reservation:
    rid: int
    member_id: int
    book: str


class ReserveStore:
    def __init__(self, copies_available: dict[str, int]):
        self.copies_available = copies_available
        self.items: dict[int, Reservation] = {}
        self._next = 1

    def active_for(self, member_id: int) -> list[Reservation]:
        return [r for r in self.items.values() if r.member_id == member_id]


def reserve(store: ReserveStore, member_id: int, book: str) -> Reservation:
    if len(store.active_for(member_id)) >= MAX_RESERVATIONS:
        raise ReserveLimitError("预约已满")
    r = Reservation(store._next, member_id, book)
    store.items[r.rid] = r
    store._next += 1
    return r


def cancel_reservation(store: ReserveStore, rid: int) -> None:
    """删除一条预约。调用方负责先核对归属。"""
    del store.items[rid]
