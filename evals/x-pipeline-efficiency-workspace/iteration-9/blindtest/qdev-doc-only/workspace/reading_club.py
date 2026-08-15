"""读书会小程序核心逻辑（本地内存版）。"""
import random
import string
from datetime import date, timedelta


class ClubError(Exception):
    """读书会业务错误，message 直接展示给用户。"""


class Group:
    _next_id = 1

    def __init__(self, name, book, owner_id, invite_code):
        self.id = f"g{Group._next_id}"
        Group._next_id += 1
        self.name = name
        self.book = book
        self.owner_id = owner_id
        self.invite_code = invite_code
        self.members = []       # user_id，按加入顺序
        self.nicknames = {}     # user_id -> 昵称
        self.checkins = {}      # user_id -> {date: (start, end, note)}
        self.members.append(owner_id)
        self.nicknames[owner_id] = f"{owner_id}"

    def add_member(self, user_id, nickname):
        self.members.append(user_id)
        self.nicknames[user_id] = nickname

    def check_in(self, user_id, start_page, end_page, note, day=None):
        if user_id not in self.members:
            raise ClubError("只有小组成员可以打卡")
        if not note or not note.strip():
            raise ClubError("请写几句感想")
        if start_page > end_page:
            raise ClubError("起始页不能大于结束页")
        day = day or date.today()
        records = self.checkins.setdefault(user_id, {})
        if day in records:
            raise ClubError("今天已经打过卡了")
        records[day] = (start_page, end_page, note.strip())

    def streak_days(self, user_id, today=None):
        today = today or date.today()
        days = self.checkins.get(user_id, {})
        if not days:
            return 0
        streak = 0
        d = today
        if d not in days:
            d = today - timedelta(days=1)
        while d in days:
            streak += 1
            d -= timedelta(days=1)
        return streak


class ReadingClub:
    MAX_GROUPS_PER_USER = 5

    def __init__(self):
        self._groups_by_code = {}   # invite_code -> Group
        self._groups_by_id = {}     # group_id -> Group
        self._user_groups = {}      # user_id -> [group_id, ...]

    def create_group(self, owner_id, group_name, book):
        if not group_name or not group_name.strip():
            raise ClubError("请填写小组名字")
        if not book or not book.strip():
            raise ClubError("请选择要读的书")
        code = self._new_code()
        group = Group(group_name.strip(), book.strip(), owner_id, code)
        self._groups_by_code[code] = group
        self._groups_by_id[group.id] = group
        self._user_groups.setdefault(owner_id, []).append(group.id)
        return group

    def _new_code(self):
        while True:
            code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if code not in self._groups_by_code:
                return code

    def join_group(self, user_id, invite_code, nickname):
        group = self._groups_by_code.get(invite_code)
        if group is None:
            raise ClubError("邀请码无效")
        if not nickname or not nickname.strip():
            raise ClubError("请填写昵称")
        if user_id in group.members:
            raise ClubError("你已经在这个小组里了")
        if len(self._user_groups.get(user_id, [])) >= self.MAX_GROUPS_PER_USER:
            raise ClubError("最多只能同时加入 5 个小组")
        group.add_member(user_id, nickname.strip())
        self._user_groups.setdefault(user_id, []).append(group.id)
        return group

    def groups_of(self, user_id):
        return [self._groups_by_id[gid] for gid in self._user_groups.get(user_id, [])]
