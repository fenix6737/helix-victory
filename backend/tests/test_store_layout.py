"""店舗レイアウト — 角台判定"""

from __future__ import annotations

import unittest

from app.store_layout import get_machine_position, infer_position_with_store


class TestStoreLayout(unittest.TestCase):
    def test_kicona_e_ghoul_block_corner(self):
        self.assertEqual(get_machine_position("kicona_amagasaki", 333), "corner")

    def test_kicona_front_l_ghoul_corner(self):
        self.assertEqual(get_machine_position("kicona_amagasaki", 481), "corner")

    def test_infer_uses_layout_zone(self):
        pos = infer_position_with_store(481, None, "kicona_amagasaki")
        self.assertEqual(pos, "corner")

    def test_tail_fallback(self):
        pos = infer_position_with_store(101, None, "unknown_store")
        self.assertEqual(pos, "corner2")


if __name__ == "__main__":
    unittest.main()
