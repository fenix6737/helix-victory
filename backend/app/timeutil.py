"""日付は JST 基準（表示・分析のズレ防止）"""

from datetime import date, datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))


def jst_now() -> datetime:
    return datetime.now(JST)


def jst_today() -> date:
    return jst_now().date()


def analysis_target_date() -> date:
    """
    推奨対象日。
    22時以降は翌日営業分として翌日を対象にする（従来ロジックをJST化）。
    """
    now = jst_now()
    if now.hour >= 22:
        return now.date() + timedelta(days=1)
    return now.date()
