"""開発者指示書 §1 — 必須データソース URL の実装確認（ダミー禁止）"""
from __future__ import annotations

import os
import unittest

from collector.anaslo.client import LIST_URL_DEFAULT
from collector.hallnavi.client import DEFAULT_URL as HALLNAVI_URL
from collector.minrepo.client import TAG_URL_DEFAULT
from collector.pscube.client import DEFAULT_URL as PSCUBE_URL


class DeveloperSpecSourceUrls(unittest.TestCase):
    def test_anaslo_kicona_listing(self):
        self.assertIn("ana-slo.com", LIST_URL_DEFAULT)
        self.assertIn("%E5%85%B5%E5%BA%AB", LIST_URL_DEFAULT)  # 兵庫県（URLエンコード）
        env = os.getenv(
            "ANASLO_KICONA_LIST_URL",
            "https://ana-slo.com/ホールデータ/兵庫県/キコーナ尼崎本店-データ一覧/",
        )
        self.assertIn("ana-slo.com", env)

    def test_pscube_url(self):
        self.assertIn("pscube.jp", PSCUBE_URL)
        self.assertIn("c713842", PSCUBE_URL)

    def test_minrepo_tag_url(self):
        self.assertIn("min-repo.com", TAG_URL_DEFAULT)
        self.assertIn("tag", TAG_URL_DEFAULT)

    def test_hall_navi_url(self):
        self.assertIn("hall-navi.com", HALLNAVI_URL)
        self.assertIn("660088400000027290", HALLNAVI_URL)

    def test_kicona_integrates_sources(self):
        import inspect

        from collector import kicona

        src = inspect.getsource(kicona.scrape_kicona_amagasaki)
        for needle in ("scrape_anaslo_store", "scrape_pscube_store", "scrape_minrepo_store", "fetch_hall_navi_info"):
            self.assertIn(needle, src, f"missing integration: {needle}")


if __name__ == "__main__":
    unittest.main()
