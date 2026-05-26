"""
LLM による推奨理由の自然文補助（ランキング決定には不使用）。
OPENAI_API_KEY 未設定時はルール理由をそのまま返す。
"""

import json
import logging
import os

import httpx

logger = logging.getLogger("explanation")


async def enrich_reasons(
    title: str,
    machine_number: int,
    score: float,
    rule_reasons: list[str],
) -> list[str]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return rule_reasons

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    prompt = (
        f"パチスロ分析の推奨理由を、スマホで3秒で読める短い日本語に整えてください。\n"
        f"機種: {title} / 台番: {machine_number} / 推奨スコア: {score}\n"
        f"根拠（変更・追加禁止、言い換えのみ）: {json.dumps(rule_reasons, ensure_ascii=False)}\n"
        f"出力: 箇条書き最大4行、各行は「・」で始める。数値の捏造禁止。"
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "あなたは説明文を短く整える補助AIです。"},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 200,
                    "temperature": 0.2,
                },
            )
            res.raise_for_status()
            text = res.json()["choices"][0]["message"]["content"]
            lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("・")]
            return lines if lines else rule_reasons
    except Exception as e:
        logger.warning("LLM explanation skipped: %s", e)
        return rule_reasons
