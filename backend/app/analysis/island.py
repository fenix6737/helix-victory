"""島ID推定・島単位集計（単台分析禁止のため必須）"""

import pandas as pd


def infer_island_id(machine_number: int, store_id: str) -> str:
    """台番号から島を推定（店舗マップ未登録時の本番ヒューリスティック）"""
    if store_id == "kicona_amagasaki":
        # 例: 521 → island_5xx (百の位ブロック)
        block = (machine_number // 100) * 100
        return f"island_{block}"
    if store_id == "maruhan_umeda":
        block = (machine_number // 100) * 100
        return f"island_{block}"
    return f"island_{machine_number // 50 * 50}"


def enrich_island_column(df: pd.DataFrame, store_id: str) -> pd.DataFrame:
    df = df.copy()
    if "island_id" not in df.columns:
        df["island_id"] = None
    mask = df["island_id"].isna() | (df["island_id"] == "")
    if "machine_number" in df.columns:
        df.loc[mask, "island_id"] = df.loc[mask, "machine_number"].apply(
            lambda n: infer_island_id(int(n), store_id)
        )
    return df


def compute_island_stats(df: pd.DataFrame, target_date) -> pd.DataFrame:
    """島単位の稼働・差枚・波形サマリ"""
    if df.empty or "island_id" not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    df["captured_at"] = pd.to_datetime(df["captured_at"], utc=True)
    recent = df[df["captured_at"].dt.date >= (target_date - pd.Timedelta(days=3))]

    rows = []
    for island_id, g in recent.groupby("island_id"):
        if pd.isna(island_id):
            continue
        diffs = g["diff_coins"].dropna()
        rots = g["rotation_count"].dropna()
        rows.append(
            {
                "island_id": str(island_id),
                "island_mean_diff": float(diffs.mean()) if len(diffs) else 0.0,
                "island_ops_rate": float(g["is_operating"].mean()) if "is_operating" in g else 0.5,
                "island_machine_count": g["machine_id"].nunique(),
                "island_release_signal": 1.0 if len(diffs) >= 3 and diffs.iloc[-1] > diffs.mean() + 200 else 0.0,
                "island_recovery_signal": 1.0 if len(diffs) >= 3 and diffs.iloc[-1] < -500 else 0.0,
            }
        )
    return pd.DataFrame(rows)
