"""台データ HTML パーサーのユニットテスト"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from collector.daidata.parser import parse_all_list_html

SAMPLE_HTML = """
<html><body>
<table class="tablesorter">
<thead><tr>
<th></th><th>台番号</th><th>貸玉</th><th>機種名</th><th>BB回数</th><th>RB回数</th><th>差枚</th>
</tr></thead>
<tbody>
<tr><td></td><td>521</td><td>46</td><td>Lスマスロ北斗</td><td>12</td><td>28</td><td>-1200</td></tr>
<tr><td></td><td>522</td><td>46</td><td>Lスマスロ北斗</td><td>8</td><td>15</td><td>800</td></tr>
</tbody>
</table>
</body></html>
"""


def test_parse_tablesorter():
    rows = parse_all_list_html(SAMPLE_HTML, "maruhan_umeda", hist_num=1)
    assert len(rows) == 2
    assert rows[0]["machine_number"] == 521
    assert rows[0]["title"] == "Lスマスロ北斗"
    assert rows[0]["diff_coins"] == -1200
    assert rows[0]["big_count"] == 12
    assert rows[0]["reg_count"] == 28


if __name__ == "__main__":
    test_parse_tablesorter()
    print("ok")
