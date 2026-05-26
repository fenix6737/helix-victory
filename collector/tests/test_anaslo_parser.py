import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from collector.anaslo.parser import parse_day_machines, parse_listing_day_links

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "samples")


def test_parse_listing():
    with open(os.path.join(SAMPLES, "anaslo_kicona.html"), encoding="utf-8") as f:
        html = f.read()
    days = parse_listing_day_links(html, limit=5)
    assert len(days) >= 3
    assert days[0]["date"]


def test_parse_day():
    with open(os.path.join(SAMPLES, "anaslo_day.html"), encoding="utf-8") as f:
        html = f.read()
    captured = datetime(2026, 5, 14, 13, 0, tzinfo=timezone.utc)
    rows = parse_day_machines(html, "kicona_amagasaki", captured)
    assert len(rows) >= 280
    assert rows[0]["big_count"] is not None or rows[0]["diff_coins"] is not None
    assert rows[0]["source"] == "anaslo"


def test_parse_rotation_column():
    html = """
    <table class="fixed_get_medals_table">
      <tr><th>台番</th><th>機種</th><th>差枚</th><th>回転</th><th>BB</th></tr>
      <tr><td>1</td><td>テスト機</td><td>100</td><td>5200</td><td>2</td></tr>
    </table>
    """
    captured = datetime(2026, 5, 20, 4, 0, tzinfo=timezone.utc)
    rows = parse_day_machines(html, "kicona_amagasaki", captured)
    assert len(rows) == 1
    assert rows[0]["rotation_count"] == 5200


if __name__ == "__main__":
    test_parse_listing()
    test_parse_day()
    print("ok")
