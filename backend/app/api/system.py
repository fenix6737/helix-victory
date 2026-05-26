"""公開URLなど — 認証不要のシステム情報"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/system", tags=["system"])

# backend/app/api/system.py -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]
_PUBLIC_URL_JSON = _REPO_ROOT / "data" / "public-url.json"


@router.get("/public-url")
async def get_public_url():
    """PC起動スクリプトが書き込む最新の公開URL（welcome 画面用）"""
    if not _PUBLIC_URL_JSON.is_file():
        return {
            "available": False,
            "welcome_url": None,
            "public_url": None,
            "mode": None,
            "note": "公開URLはまだありません。Start Helix Victory.bat で起動してください。",
        }
    try:
        data = json.loads(_PUBLIC_URL_JSON.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError):
        return {"available": False, "welcome_url": None, "public_url": None, "mode": None}

    welcome = data.get("welcome_url") or data.get("public_url")
    return {
        "available": bool(welcome),
        "welcome_url": welcome,
        "login_url": data.get("login_url"),
        "public_url": data.get("public_url"),
        "local_url": data.get("local_url"),
        "lan_url": data.get("lan_url"),
        "mode": data.get("mode"),
        "updated_at": data.get("updated_at"),
        "note": data.get("note"),
    }
