import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from collector.minrepo.parser import parse_all_machines, parse_tag_report_links
from datetime import datetime, timezone

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "samples")


def test_parse_tag_links():
    with open(os.path.join(SAMPLES, "minrepo_tag.html"), encoding="utf-8") as f:
        html = f.read()
    reports = parse_tag_report_links(html, limit=5)
    assert len(reports) >= 3
    assert all(r["post_id"].isdigit() for r in reports)
    assert "min-repo.com" in reports[0]["url"]


def test_parse_all_machines():
    with open(os.path.join(SAMPLES, "minrepo_all.html"), encoding="utf-8") as f:
        html = f.read()
    captured = datetime(2026, 3, 26, 13, 0, tzinfo=timezone.utc)
    rows = parse_all_machines(html, "kicona_amagasaki", captured)
    assert len(rows) >= 200
    assert rows[0]["machine_number"] > 0
    assert rows[0]["title"]
    assert rows[0]["diff_coins"] is not None
    assert rows[0]["final_games"] is not None
    assert rows[0]["source"] == "minrepo"


if __name__ == "__main__":
    test_parse_tag_links()
    test_parse_all_machines()
    print("ok")
