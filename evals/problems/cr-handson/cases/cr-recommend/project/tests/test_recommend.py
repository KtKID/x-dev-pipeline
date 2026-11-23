import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from library import recommend  # noqa: E402
from library.auth import Member  # noqa: E402
from library.history import HistoryStore  # noqa: E402


def test_recommend_same_category():
    recommend._cache.clear()
    history = HistoryStore()
    history.add(10, "三体")
    lines = recommend.get_recommendations(Member(10, "科幻"), history)
    assert "因为你借过《三体》，推荐《沙丘》" in lines
