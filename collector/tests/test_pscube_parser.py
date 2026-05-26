import unittest
from pathlib import Path

from collector.pscube.parser import parse_pscube_machines

SAMPLE = """
<html><body>
<table>
<tr><th>台番</th><th>機種</th><th>差枚</th><th>BB</th><th>RB</th></tr>
<tr><td>101</td><td>L 東京喰種</td><td>+1200</td><td>3</td><td>1</td></tr>
<tr><td>205</td><td>新世紀エヴァンゲリオン</td><td>-400</td><td>0</td><td>2</td></tr>
</table>
</body></html>
"""


class TestPscubeParser(unittest.TestCase):
    def test_parse_table(self):
        rows = parse_pscube_machines(SAMPLE, "kicona_amagasaki")
        self.assertEqual(len(rows), 2)
        nums = {r["machine_number"] for r in rows}
        self.assertIn(101, nums)
        self.assertIn(205, nums)
        self.assertEqual(rows[0]["source"], "pscube")


if __name__ == "__main__":
    unittest.main()
