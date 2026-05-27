"""グラフ細部パース"""

from __future__ import annotations

import unittest

from app.analysis.graph_intraday import parse_graph_html_snippet, parse_graph_samples
from app.analysis.machine_borders import BorderSpec


class TestGraphIntraday(unittest.TestCase):
    def test_parse_json_list(self):
        raw = '[{"t": 0, "diff": -100}, {"t": 1, "diff": 200}]'
        self.assertEqual(len(parse_graph_samples(raw)), 2)

    def test_parse_html_points(self):
        html = '<div data-points="[[0,-50],[1,100],[2,300]]"></div>'
        pts = parse_graph_html_snippet(html)
        self.assertGreaterEqual(len(pts), 2)


if __name__ == "__main__":
    unittest.main()
