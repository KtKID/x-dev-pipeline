"""推荐书单。为了快，结果按缓存键缓存。"""
from library.auth import Member
from library.history import CATALOG, HistoryStore

_cache: dict[str, list[str]] = {}


def _cache_key(member: Member) -> str:
    return f"rec:{member.favorite_category}"


def _build(member: Member, history: HistoryStore) -> list[str]:
    read = history.books_of(member.member_id)
    lines = []
    for book in read:
        for other, category in CATALOG.items():
            if category == CATALOG.get(book) and other not in read:
                lines.append(f"因为你借过《{book}》，推荐《{other}》")
    return lines


def get_recommendations(member: Member, history: HistoryStore) -> list[str]:
    key = _cache_key(member)
    if key not in _cache:
        _cache[key] = _build(member, history)
    return _cache[key]
