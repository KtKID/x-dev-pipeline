"""读书会已有功能测试。"""
import unittest
from datetime import date

from reading_club import ClubError, ReadingClub


class CreateGroupTest(unittest.TestCase):
    def test_create_group_returns_invite_code(self):
        club = ReadingClub()
        group = club.create_group("u1", "晚读小组", "三体")
        self.assertEqual(len(group.invite_code), 6)
        self.assertEqual(group.name, "晚读小组")
        self.assertEqual(group.book, "三体")
        self.assertIn("u1", group.members)

    def test_create_group_requires_name(self):
        club = ReadingClub()
        with self.assertRaises(ClubError) as ctx:
            club.create_group("u1", "  ", "三体")
        self.assertEqual(str(ctx.exception), "请填写小组名字")

    def test_create_group_requires_book(self):
        club = ReadingClub()
        with self.assertRaises(ClubError) as ctx:
            club.create_group("u1", "晚读小组", "")
        self.assertEqual(str(ctx.exception), "请选择要读的书")


class JoinGroupTest(unittest.TestCase):
    def setUp(self):
        self.club = ReadingClub()
        self.group = self.club.create_group("u1", "晚读小组", "三体")

    def test_join_with_valid_code(self):
        g = self.club.join_group("u2", self.group.invite_code, "小明")
        self.assertIn("u2", g.members)
        self.assertEqual(g.nicknames["u2"], "小明")

    def test_join_with_invalid_code(self):
        with self.assertRaises(ClubError) as ctx:
            self.club.join_group("u2", "ZZZZZZ", "小明")
        self.assertEqual(str(ctx.exception), "邀请码无效")

    def test_join_requires_nickname(self):
        with self.assertRaises(ClubError) as ctx:
            self.club.join_group("u2", self.group.invite_code, " ")
        self.assertEqual(str(ctx.exception), "请填写昵称")

    def test_join_same_group_twice_rejected(self):
        self.club.join_group("u2", self.group.invite_code, "小明")
        with self.assertRaises(ClubError) as ctx:
            self.club.join_group("u2", self.group.invite_code, "小明2")
        self.assertEqual(str(ctx.exception), "你已经在这个小组里了")

    def test_join_fifth_group_ok_sixth_rejected(self):
        for i in range(4):
            g = self.club.create_group(f"owner{i}", f"组{i}", f"书{i}")
            self.club.join_group("u2", g.invite_code, "小明")
        self.club.join_group("u2", self.group.invite_code, "小明")
        self.assertEqual(len(self.club.groups_of("u2")), 5)
        g6 = self.club.create_group("owner9", "组9", "书9")
        with self.assertRaises(ClubError) as ctx:
            self.club.join_group("u2", g6.invite_code, "小明")
        self.assertEqual(str(ctx.exception), "最多只能同时加入 5 个小组")


class CheckInTest(unittest.TestCase):
    def setUp(self):
        self.club = ReadingClub()
        self.group = self.club.create_group("u1", "晚读小组", "三体")
        self.club.join_group("u2", self.group.invite_code, "小明")

    def test_check_in_records_pages_and_note(self):
        day = date(2026, 8, 1)
        self.group.check_in("u1", 10, 25, "开头很吸引人", day=day)
        self.assertEqual(self.group.checkins["u1"][day], (10, 25, "开头很吸引人"))

    def test_check_in_twice_same_day_rejected(self):
        day = date(2026, 8, 1)
        self.group.check_in("u1", 10, 25, "第一次", day=day)
        with self.assertRaises(ClubError) as ctx:
            self.group.check_in("u1", 26, 30, "第二次", day=day)
        self.assertEqual(str(ctx.exception), "今天已经打过卡了")

    def test_check_in_start_after_end_rejected(self):
        with self.assertRaises(ClubError) as ctx:
            self.group.check_in("u1", 30, 10, "页码反了", day=date(2026, 8, 1))
        self.assertEqual(str(ctx.exception), "起始页不能大于结束页")

    def test_streak_resets_after_gap(self):
        d1 = date(2026, 8, 1)
        d2 = date(2026, 8, 2)
        d4 = date(2026, 8, 4)
        self.group.check_in("u1", 1, 10, "a", day=d1)
        self.group.check_in("u1", 11, 20, "b", day=d2)
        self.assertEqual(self.group.streak_days("u1", today=d2), 2)
        self.group.check_in("u1", 21, 30, "c", day=d4)
        self.assertEqual(self.group.streak_days("u1", today=d4), 1)


if __name__ == "__main__":
    unittest.main()
