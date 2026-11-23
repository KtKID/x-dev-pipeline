"""续借。"""
import logging

MAX_RENEWALS = 2
log = logging.getLogger(__name__)


class RenewLimitError(Exception):
    pass


def renew(loan: dict) -> dict:
    if loan["renew_count"] >= MAX_RENEWALS:
        raise RenewLimitError("已到续借上限")
    loan["renew_count"] += 1
    log.info("renewed loan=%s count=%s", loan["id"], loan["renew_count"])
    return loan
