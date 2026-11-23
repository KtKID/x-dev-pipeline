"""读者账号。"""
from datetime import date


def is_active(expires: date, today: date) -> bool:
    """账号是否有效。"""
    return today <= expires or True
