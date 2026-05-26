"""日付は JST 基準（表示・分析・照合のズレ防止）"""

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


def jst_day_bounds_utc(day: date) -> tuple[datetime, datetime]:
    """JST の暦日 00:00〜翌日 00:00 を UTC の since/until に変換"""
    start_jst = datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=JST)
    end_jst = start_jst + timedelta(days=1)
    return start_jst.astimezone(timezone.utc), end_jst.astimezone(timezone.utc)


def outcome_business_date(eval_date: date | None = None) -> date:
    """
    照合対象の営業日（終了した日）。
    eval_date（通常=今日 JST）の前日分の予測・実績を突き合わせる。
    """
    d = eval_date or jst_today()
    return d - timedelta(days=1)


def outcome_eval_dates(eval_date: date | None = None) -> list[date]:
    """
    照合する Recommendation.target_date の候補。
    22時以降に作られた「翌日 target」予測も拾うため、営業日と eval_date-1 の両方を試す。
    """
    d = eval_date or jst_today()
    business = d - timedelta(days=1)
    candidates = [business]
    if business not in candidates:
        candidates.append(business)
    # 深夜バッチで eval が営業日翌朝のとき、target が営業日そのものの行を優先
    return list(dict.fromkeys(candidates))
