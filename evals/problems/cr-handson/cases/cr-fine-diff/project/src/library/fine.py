"""逾期罚款。"""
from datetime import date

PER_DAY = 50  # 分


def calc_fine(due: date, returned: date) -> int:
    """返回罚款，单位分。"""
    return 0
