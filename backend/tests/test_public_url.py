"""公開URL API — data/public-url.json 連携"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


class PublicUrlEndpointTest(unittest.TestCase):
    def test_missing_file_returns_unavailable(self):
        with patch("app.api.system._PUBLIC_URL_JSON", Path("/nonexistent/public-url.json")):
            client = TestClient(app)
            res = client.get("/api/v1/system/public-url")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertFalse(body["available"])
        self.assertIsNone(body.get("welcome_url"))

    def test_reads_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "public-url.json"
            path.write_text(
                json.dumps(
                    {
                        "welcome_url": "https://example.trycloudflare.com/welcome",
                        "public_url": "https://example.trycloudflare.com",
                        "mode": "quick",
                    }
                ),
                encoding="utf-8",
            )
            with patch("app.api.system._PUBLIC_URL_JSON", path):
                client = TestClient(app)
                res = client.get("/api/v1/system/public-url")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["available"])
        self.assertIn("trycloudflare", body["welcome_url"])
        self.assertEqual(body["mode"], "quick")


if __name__ == "__main__":
    unittest.main()
