import os

import httpx

from collector.http_retry import is_retryable_http, with_retries


async def post_logs(api_url: str, store_id: str, logs: list[dict]) -> dict:
    api_key = os.getenv("INGEST_API_KEY", os.getenv("ingest_api_key", ""))
    headers = {"X-Ingest-Key": api_key} if api_key else {}

    async def _once() -> dict:
        async with httpx.AsyncClient(timeout=120.0) as client:
            res = await client.post(
                f"{api_url}/api/v1/ingest/logs",
                json={"store_id": store_id, "logs": logs},
                headers=headers,
            )
            res.raise_for_status()
            return res.json()

    return await with_retries(_once, retry_on=is_retryable_http)
