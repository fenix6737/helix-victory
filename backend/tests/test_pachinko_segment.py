"""4パチミドル以上フィルタ"""

from __future__ import annotations

import unittest

from app.pachinko_segment import pachinko_analysis_eligible


class TestPachinkoSegment(unittest.TestCase):
    def test_exclude_1pachi(self):
        self.assertFalse(pachinko_analysis_eligible("1パチンコ 海物語"))
        self.assertFalse(pachinko_analysis_eligible("P海物語 1円"))

    def test_exclude_light(self):
        self.assertFalse(pachinko_analysis_eligible("P甘デジ からくり"))
        self.assertFalse(pachinko_analysis_eligible("ライトミドル 北斗"))

    def test_include_middle(self):
        self.assertTrue(pachinko_analysis_eligible("Pエヴァンゲリオン未来への咆哮"))
        self.assertTrue(pachinko_analysis_eligible("4パチ ミドル 東京喰種"))

    def test_slot_always_eligible(self):
        self.assertTrue(pachinko_analysis_eligible("マイジャグラーV"))

    def test_e_prefix(self):
        self.assertTrue(pachinko_analysis_eligible("e バイオハザード6"))


if __name__ == "__main__":
    unittest.main()
