"""daidata セッション検証"""

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger("daidata.session")


class DaidataSessionError(Exception):
    """ログイン切れ・契約外"""


def is_logged_in_html(html: str) -> bool:
    if not html or len(html) < 500:
        return False
    lower = html.lower()
    if "login" in lower and "tablesorter" not in lower:
        return False
    if "ログイン" in html and "all_list" not in lower and "tablesorter" not in lower:
        return False
    if "tablesorter" in html or "台番号" in html or "差枚" in html:
        return True
    return False


def storage_age_hours(path: str | None) -> float | None:
    if not path or not os.path.isfile(path):
        return None
    mtime = os.path.getmtime(path)
    age = datetime.now(timezone.utc) - datetime.fromtimestamp(mtime, tz=timezone.utc)
    return age.total_seconds() / 3600


def validate_storage(path: str | None, max_age_hours: float = 168.0) -> None:
    if not path or not os.path.isfile(path):
        raise DaidataSessionError(
            "DAIDATA_STORAGE_STATE がありません。"
            " python scripts/daidata_login.py でログイン保存してください。"
        )
    age = storage_age_hours(path)
    if age is not None and age > max_age_hours:
        logger.warning("storage state が %.0f 時間経過 — 再ログイン推奨", age)
