import unittest

from app.featured import classify_featured


class TestFeatured(unittest.TestCase):
    def test_tokyo_ghoul(self):
        ok, gid, badge = classify_featured("L 東京喰種")
        self.assertTrue(ok)
        self.assertEqual(gid, "tokyo_ghoul")
        self.assertEqual(badge, "喰種")

    def test_evangelion(self):
        ok, gid, badge = classify_featured("新世紀エヴァンゲリオン")
        self.assertTrue(ok)
        self.assertEqual(gid, "evangelion")

    def test_normal(self):
        ok, gid, _ = classify_featured("ハナハナ")
        self.assertFalse(ok)
        self.assertIsNone(gid)


if __name__ == "__main__":
    unittest.main()
